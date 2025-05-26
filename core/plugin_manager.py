# plugin_manager.py
import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path
from typing import Dict, Type, Optional, List, Tuple, TYPE_CHECKING, Any, Set

if TYPE_CHECKING:
    from main import SerialDebugger  # Forward reference for type hinting
    from core.panel_interface import PanelInterface  # Actual import for PanelInterface

class PluginManager:
    """
    Manages the discovery, registration, and instantiation of panel plugins.
    Enhanced to support session-level blocking and selective enabling of plugins.
    """

    def __init__(self, main_window_ref: 'SerialDebugger'):
        """
        Initializes the PluginManager.

        Args:
            main_window_ref: A reference to the main SerialDebugger application instance.
        """
        self.main_window_ref = main_window_ref
        self.error_logger = main_window_ref.error_logger

        # Stores: {panel_type_name: (PanelClass, display_name, module_name)}
        self.registered_panel_types: Dict[str, Tuple[Type['PanelInterface'], str, str]] = {}

        # Stores full module names (e.g., "panel_plugins.my_plugin") that are blocked for the current session.
        self.session_blocklisted_modules: Set[str] = set()

        # Stores full module names that are explicitly enabled by the user/config.
        # This list should be populated by SerialDebugger from its configuration.
        self.enabled_plugin_modules: Set[str] = set()  # SerialDebugger will manage this list

        # Stores panel configs before a reload attempt
        self._active_panel_configs_before_reload: Dict[str, List[Dict[str, Any]]] = {}

    def update_enabled_plugins(self, enabled_modules: Set[str]):
        """
        Called by SerialDebugger to update the list of enabled plugin modules.
        Args:
            enabled_modules: A set of full module names that should be considered enabled.
        """
        self.enabled_plugin_modules = enabled_modules
        if self.error_logger:
            self.error_logger.log_info(f"PluginManager: Enabled plugins list updated: {enabled_modules}")

    def register_panel_type(self, panel_class: Type['PanelInterface'], module_name: str) -> None:
        """
        Registers a panel class with the manager.
        """
        from core.panel_interface import PanelInterface

        if not issubclass(panel_class, PanelInterface):
            if self.error_logger:
                self.error_logger.log_error(
                    f"Panel class {panel_class.__name__} from module {module_name} does not inherit from PanelInterface. Registration failed.",
                    "PLUGIN_MANAGER"
                )
            return

        type_name = getattr(panel_class, 'PANEL_TYPE_NAME', None)
        display_name = getattr(panel_class, 'PANEL_DISPLAY_NAME', None)

        if not type_name or type_name == PanelInterface.PANEL_TYPE_NAME:
            if self.error_logger:
                self.error_logger.log_error(
                    f"Panel class {panel_class.__name__} from module {module_name} must define a unique PANEL_TYPE_NAME. Registration failed.",
                    "PLUGIN_MANAGER"
                )
            return
        if not display_name or display_name == PanelInterface.PANEL_DISPLAY_NAME:
            if self.error_logger:
                self.error_logger.log_error(
                    f"Panel class {panel_class.__name__} from module {module_name} must define PANEL_DISPLAY_NAME. Registration failed.",
                    "PLUGIN_MANAGER"
                )
            return

        if type_name in self.registered_panel_types:
            old_class, old_display_name, old_module_name = self.registered_panel_types[type_name]
            if self.error_logger:
                self.error_logger.log_warning(
                    f"Panel type '{type_name}' (from {panel_class.__name__} in {module_name}) is already registered "
                    f"(was {old_class.__name__} from {old_module_name}). Overwriting with new definition.",
                    "PLUGIN_MANAGER"
                )
        self.registered_panel_types[type_name] = (panel_class, display_name, module_name)
        if self.error_logger:
            self.error_logger.log_info(
                f"Registered panel type: '{type_name}' ({display_name}) from class {panel_class.__name__} in module {module_name}"
            )

    def unregister_panel_type(self, panel_type_name: str) -> bool:
        """
        Unregisters a panel type.
        """
        if panel_type_name in self.registered_panel_types:
            panel_class, display_name, module_name = self.registered_panel_types.pop(panel_type_name)
            if self.error_logger:
                self.error_logger.log_info(
                    f"Unregistered panel type: '{panel_type_name}' ({display_name}) from class {panel_class.__name__} in module {module_name}."
                )
            return True
        return False

    def block_module_for_session(self, module_name: str) -> List[str]:
        """
        Blocks a module for the current session, preventing it from being loaded/reloaded.
        Also unregisters any panel types currently registered from this module.

        Args:
            module_name: The full name of the module to block (e.g., "panel_plugins.my_plugin").

        Returns:
            A list of panel_type_names that were unregistered as a result.
        """
        unregistered_types: List[str] = []
        if module_name not in self.session_blocklisted_modules:
            self.session_blocklisted_modules.add(module_name)
            if self.error_logger:
                self.error_logger.log_info(f"模块 {module_name} 已添加到当前会话的阻止列表。", "PLUGIN_MANAGER")

        # Unregister any types from this module
        types_to_remove = [
            pt_name for pt_name, (_, _, mod_name) in self.registered_panel_types.items()
            if mod_name == module_name
        ]
        for pt_name_to_remove in types_to_remove:
            if self.unregister_panel_type(pt_name_to_remove):
                unregistered_types.append(pt_name_to_remove)

        # Also remove from enabled list if it was there
        if module_name in self.enabled_plugin_modules:
            self.enabled_plugin_modules.discard(module_name)
            # SerialDebugger should be notified to update its persistent config for enabled plugins
            if hasattr(self.main_window_ref, 'update_enabled_plugin_config'):
                self.main_window_ref.update_enabled_plugin_config(self.enabled_plugin_modules)

        return unregistered_types

    def unblock_module_for_session(self, module_name: str):
        """
        Removes a module from the session blocklist.
        The module will be eligible for discovery on the next plugin scan if it's also enabled.
        """
        if module_name in self.session_blocklisted_modules:
            self.session_blocklisted_modules.remove(module_name)
            if self.error_logger:
                self.error_logger.log_info(f"模块 {module_name} 已从当前会话的阻止列表中移除。", "PLUGIN_MANAGER")
        # Note: This does not automatically re-enable or reload the plugin.
        # A call to discover_plugins (potentially with reload_modules=True) and ensuring
        # it's in the enabled_plugin_modules list is needed.

    def discover_plugins(self, plugin_dir_name: str = "panel_plugins", reload_modules: bool = False,
                         load_only_enabled: bool = True) -> List[str]:
        """
        Discovers and attempts to load/reload panel plugins.

        Args:
            plugin_dir_name: Directory for plugins.
            reload_modules: If True, attempts to reload already imported (and enabled) modules.
            load_only_enabled: If True, only imports/registers modules listed in self.enabled_plugin_modules.
                               If False, attempts to load all found (not blocklisted) modules.
                               (Useful for an initial scan to populate a management UI).

        Returns:
            A list of panel_type_names that were successfully (re)registered.
        """
        script_dir = Path(__file__).resolve().parent
        plugins_path = script_dir.parent / plugin_dir_name

        if not plugins_path.is_dir():
            if self.error_logger:
                self.error_logger.log_info(f"插件目录 '{plugins_path}' 未找到。")
            return []

        if self.error_logger:
            self.error_logger.log_info(f"正在扫描插件目录: {plugins_path}")

        successfully_registered_types: List[str] = []

        for finder, name, ispkg in pkgutil.iter_modules([str(plugins_path)]):
            if ispkg:
                full_module_name = f"{plugin_dir_name}.{name}"

                # 调试信息
                if self.error_logger:
                    self.error_logger.log_debug(
                        f"处理模块: {full_module_name}, "
                        f"被阻止: {full_module_name in self.session_blocklisted_modules}, "
                        f"仅加载启用: {load_only_enabled}, "
                        f"已启用: {full_module_name in self.enabled_plugin_modules}",
                        "PLUGIN_DISCOVERY"
                    )

                if full_module_name in self.session_blocklisted_modules:
                    if self.error_logger:
                        self.error_logger.log_debug(f"模块 {full_module_name} 在会话阻止列表中，跳过。",
                                                    "PLUGIN_DISCOVERY")
                    continue

                if load_only_enabled and full_module_name not in self.enabled_plugin_modules:
                    if self.error_logger:
                        self.error_logger.log_debug(
                            f"模块 {full_module_name} 已发现但未启用，跳过加载。", "PLUGIN_DISCOVERY")
                    continue

                # At this point, module is not blocklisted, and (if load_only_enabled) it is enabled.
                module_already_loaded_in_sys = full_module_name in sys.modules
                plugin_module_ref = None

                # 处理模块重载
                if reload_modules and module_already_loaded_in_sys:
                    if self.error_logger:
                        self.error_logger.log_info(f"尝试重载已启用模块: {full_module_name}",
                                                   "PLUGIN_DISCOVERY")
                    try:
                        # 卸载旧的面板类型
                        types_to_remove = [
                            pt_name for pt_name, (_, _, mod_name) in self.registered_panel_types.items()
                            if mod_name == full_module_name
                        ]
                        for pt_name_to_remove in types_to_remove:
                            self.unregister_panel_type(pt_name_to_remove)

                        plugin_module_ref = importlib.reload(sys.modules[full_module_name])
                        if self.error_logger:
                            self.error_logger.log_info(f"成功重载模块: {full_module_name}")
                    except Exception as e:
                        if self.error_logger:
                            self.error_logger.log_error(f"重载模块 {full_module_name} 失败: {e}",
                                                        "PLUGIN_DISCOVERY", exc_info=True)
                        # 重载失败时的清理工作
                        self._handle_failed_module_reload(full_module_name)
                        continue

                # 处理模块首次导入
                elif not module_already_loaded_in_sys:
                    if self.error_logger:
                        self.error_logger.log_info(f"尝试导入新模块: {full_module_name}",
                                                   "PLUGIN_DISCOVERY")
                    try:
                        plugin_module_ref = importlib.import_module(full_module_name)
                        if self.error_logger:
                            self.error_logger.log_info(f"成功导入模块: {full_module_name}")
                    except Exception as e:
                        if self.error_logger:
                            self.error_logger.log_error(f"导入新模块 {full_module_name} 失败: {e}",
                                                        "PLUGIN_DISCOVERY", exc_info=True)
                        continue

                # 处理已加载但需要重新注册的情况
                elif module_already_loaded_in_sys and not reload_modules:
                    plugin_module_ref = sys.modules[full_module_name]
                    if self.error_logger:
                        self.error_logger.log_debug(
                            f"模块 {full_module_name} 已加载，将检查注册状态。", "PLUGIN_DISCOVERY")

                # 注册插件面板
                if plugin_module_ref:
                    registered_types = self._register_module_panels(plugin_module_ref, full_module_name)
                    successfully_registered_types.extend(registered_types)

        return list(set(successfully_registered_types))

    def _handle_failed_module_reload(self, module_name: str):
        """处理模块重载失败的清理工作"""
        # 将失败的模块添加到会话阻止列表
        self.block_module_for_session(module_name)

        # 尝试从sys.modules中移除损坏的模块引用
        if module_name in sys.modules:
            try:
                del sys.modules[module_name]
                if self.error_logger:
                    self.error_logger.log_info(f"已从sys.modules中移除损坏的模块: {module_name}")
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_warning(f"无法从sys.modules中移除模块 {module_name}: {e}")

    def _register_module_panels(self, plugin_module_ref, full_module_name: str) -> List[str]:
        """注册模块中的面板类型"""
        registered_types = []

        if hasattr(plugin_module_ref, 'register_plugin_panels') and callable(
                plugin_module_ref.register_plugin_panels):
            try:
                plugin_module_ref.register_plugin_panels(self)
                current_module_types = [
                    pt_name for pt_name, (_, _, mod_name) in self.registered_panel_types.items()
                    if mod_name == full_module_name
                ]
                registered_types.extend(current_module_types)

                if self.error_logger:
                    self.error_logger.log_info(
                        f"成功注册模块: {full_module_name}. 类型: {current_module_types}",
                        "PLUGIN_DISCOVERY")
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(
                        f"调用模块 {full_module_name} 的 register_plugin_panels 时出错: {e}",
                        "PLUGIN_DISCOVERY", exc_info=True)
        else:
            if self.error_logger:
                self.error_logger.log_warning(
                    f"模块 {full_module_name} 没有可调用的 'register_plugin_panels' 函数。",
                    "PLUGIN_DISCOVERY")

        return registered_types

    def get_all_discovered_plugin_modules_metadata(self, plugin_dir_name: str = "panel_plugins") -> List[
        Dict[str, Any]]:
        """
        Scans the plugin directory and attempts to get metadata from each potential plugin module
        without fully loading/registering them unless they define a specific metadata function.
        This is useful for a plugin management UI.

        Returns:
            A list of dictionaries, each representing a discovered plugin module with its metadata.
        """
        script_dir = Path(__file__).resolve().parent
        plugins_path = script_dir.parent / plugin_dir_name

        # 调试信息
        if self.error_logger:
            self.error_logger.log_debug(
                f"扫描插件元数据，路径: {plugins_path.resolve()}", "PLUGIN_DISCOVERY")

        discovered_plugins_metadata: List[Dict[str, Any]] = []

        if not plugins_path.is_dir():
            if self.error_logger:
                self.error_logger.log_warning(f"插件目录不存在: {plugins_path.resolve()}")
            return []

        # 检查目录内容
        try:
            dir_contents = list(plugins_path.iterdir())
            if self.error_logger:
                self.error_logger.log_debug(f"插件目录内容: {[item.name for item in dir_contents]}")
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"无法读取插件目录内容: {e}")
            return []

        for finder, name, ispkg in pkgutil.iter_modules([str(plugins_path)]):
            if ispkg:
                full_module_name = f"{plugin_dir_name}.{name}"
                module_metadata = self._get_module_metadata(full_module_name, name)
                discovered_plugins_metadata.append(module_metadata)

        if self.error_logger:
            self.error_logger.log_info(f"发现 {len(discovered_plugins_metadata)} 个插件模块")

        return discovered_plugins_metadata

    def _get_module_metadata(self, full_module_name: str, name: str) -> Dict[str, Any]:
        """获取单个模块的元数据"""
        module_metadata: Dict[str, Any] = {
            "module_name": full_module_name,
            "display_name": name,
            "description": "N/A",
            "version": "N/A",
            "panel_types_info": [],
            "status": "discovered"
        }

        # 确定状态
        if full_module_name in self.session_blocklisted_modules:
            module_metadata["status"] = "blocklisted (session)"
        elif full_module_name in self.enabled_plugin_modules:
            module_metadata["status"] = "enabled"
        else:
            module_metadata["status"] = "disabled"

        # 尝试获取元数据
        try:
            if full_module_name in sys.modules:
                # 如果模块已加载，直接从中获取信息
                loaded_mod = sys.modules[full_module_name]
                self._extract_metadata_from_loaded_module(loaded_mod, module_metadata)
            else:
                # 尝试安全地获取元数据而不执行模块
                self._safely_get_module_metadata(full_module_name, module_metadata)

        except Exception as e:
            if self.error_logger:
                self.error_logger.log_debug(f"获取模块元数据时出错 {full_module_name}: {e}")

        return module_metadata

    def _extract_metadata_from_loaded_module(self, loaded_mod, module_metadata: Dict[str, Any]):
        """从已加载的模块中提取元数据"""
        # 检查是否有专门的元数据函数
        if hasattr(loaded_mod, 'get_plugin_metadata') and callable(loaded_mod.get_plugin_metadata):
            try:
                meta = loaded_mod.get_plugin_metadata()
                if isinstance(meta, dict):
                    module_metadata.update(meta)
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_debug(f"调用get_plugin_metadata失败: {e}")

        # 从面板类中提取信息
        for attr_name in dir(loaded_mod):
            try:
                attr = getattr(loaded_mod, attr_name)
                if (isinstance(attr, type) and
                        hasattr(attr, 'PANEL_TYPE_NAME') and
                        hasattr(attr, 'PANEL_DISPLAY_NAME')):

                    type_name = getattr(attr, 'PANEL_TYPE_NAME')
                    if type_name and type_name != "base_panel_type":
                        module_metadata["panel_types_info"].append({
                            "type_name": type_name,
                            "display_name": getattr(attr, 'PANEL_DISPLAY_NAME', type_name)
                        })
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_debug(f"提取面板类信息时出错: {e}")

        # 如果找到了面板类型且显示名称还是默认的，则更新
        if module_metadata["panel_types_info"] and module_metadata["display_name"] == \
                module_metadata["module_name"].split('.')[-1]:
            first_panel_name = module_metadata["panel_types_info"][0]["display_name"]
            module_metadata["display_name"] = f"{first_panel_name.split(' ')[0]} 插件包"

    def _safely_get_module_metadata(self, full_module_name: str, module_metadata: Dict[str, Any]):
        """安全地获取模块元数据而不执行模块主体"""
        try:
            # 这里可以实现更安全的元数据获取方法
            # 比如解析源代码或查找特定的元数据文件
            pass
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_debug(f"安全获取元数据失败 {full_module_name}: {e}")

    def get_creatable_panel_types(self) -> Dict[str, str]:
        """
        Returns a dictionary of panel types that are registered and can be added via UI.
        """
        return {type_name: info[1] for type_name, info in self.registered_panel_types.items()}

    def create_panel_instance(self, panel_type_name: str, panel_id: int,
                              initial_config: Optional[Dict[str, Any]] = None) -> Optional['PanelInterface']:
        from core.panel_interface import PanelInterface

        if panel_type_name in self.registered_panel_types:
            panel_class, _, module_name = self.registered_panel_types[panel_type_name]
            try:
                instance = panel_class(panel_id=panel_id,
                                       main_window_ref=self.main_window_ref,
                                       initial_config=initial_config)
                if not isinstance(instance, PanelInterface):
                    if self.error_logger:
                        self.error_logger.log_error(
                            f"Instantiated panel '{panel_type_name}' (ID: {panel_id}) from module {module_name} is not a PanelInterface.",
                            "PLUGIN_MANAGER"
                        )
                    return None
                if self.error_logger:
                    self.error_logger.log_info(
                        f"Created instance of panel '{panel_type_name}' (ID: {panel_id}) from module {module_name}")
                return instance
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(
                        f"Error instantiating panel '{panel_type_name}' (ID: {panel_id}) from module {module_name}: {e}",
                        "PLUGIN_MANAGER",
                        exc_info=True
                    )
                return None
        else:
            if self.error_logger:
                self.error_logger.log_warning(
                    f"Panel type '{panel_type_name}' not found for instantiation.", "PLUGIN_MANAGER"
                )
            return None

    def get_panel_type_from_instance(self, panel_instance: 'PanelInterface') -> Optional[str]:
        return getattr(type(panel_instance), 'PANEL_TYPE_NAME', None)

    def get_module_name_for_panel_type(self, panel_type_name: str) -> Optional[str]:
        if panel_type_name in self.registered_panel_types:
            return self.registered_panel_types[panel_type_name][2]
        return None

    def clear_all_registered_types(self):
        self.registered_panel_types.clear()
        if self.error_logger:
            self.error_logger.log_info("All registered panel types have been cleared.", "PLUGIN_MANAGER")

    def store_active_panel_configs(self, active_panels: Dict[int, 'PanelInterface']):
        """存储活动面板配置以便重载后恢复"""
        self._active_panel_configs_before_reload.clear()
        for panel_id, panel_instance in active_panels.items():
            panel_type_name = self.get_panel_type_from_instance(panel_instance)
            if panel_type_name:
                if panel_type_name not in self._active_panel_configs_before_reload:
                    self._active_panel_configs_before_reload[panel_type_name] = []

                try:
                    config = panel_instance.get_config()
                    dock_widget = getattr(self.main_window_ref, 'dynamic_panel_docks', {}).get(panel_id)
                    dock_name = dock_widget.windowTitle() if dock_widget else f"Panel {panel_id}"

                    self._active_panel_configs_before_reload[panel_type_name].append({
                        "panel_id": panel_id,
                        "dock_name": dock_name,
                        "config": config
                    })
                except Exception as e:
                    if self.error_logger:
                        self.error_logger.log_warning(
                            f"无法存储面板 {panel_id} 的配置: {e}", "PLUGIN_MANAGER")

        if self.error_logger:
            self.error_logger.log_info(f"Stored configs for {len(active_panels)} active panels before reload.",
                                       "PLUGIN_MANAGER")

    def get_stored_configs_for_reload(self, panel_type_name: str) -> List[Dict[str, Any]]:
        return self._active_panel_configs_before_reload.get(panel_type_name, [])

    def clear_stored_configs(self):
        self._active_panel_configs_before_reload.clear()

    def get_plugin_status_summary(self) -> Dict[str, Any]:
        """获取插件状态摘要，用于调试和监控"""
        return {
            "registered_panel_types": len(self.registered_panel_types),
            "enabled_modules": len(self.enabled_plugin_modules),
            "blocklisted_modules": len(self.session_blocklisted_modules),
            "registered_types_list": list(self.registered_panel_types.keys()),
            "enabled_modules_list": list(self.enabled_plugin_modules),
            "blocklisted_modules_list": list(self.session_blocklisted_modules)
        }