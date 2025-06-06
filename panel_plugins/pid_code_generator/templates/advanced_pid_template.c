/**
 * @file    {{FUNCTION_PREFIX}}_pid.c (Example, actual name from generator config)
 * @author  YJ Studio Team (Generated by Advanced PID Code Generator)
 * @version 2.0.1
 * @date    {{TIMESTAMP}}
 * @brief   Advanced PID Controller Library Implementation File.
 *
 * @details This file implements the functions for an advanced PID controller
 * as declared in {{HEADER_NAME}}.
 *
 * @note    This is a template file. Placeholders like {{DATA_TYPE}},
 * {{STRUCT_NAME}}, {{FUNCTION_PREFIX}}, and {{*_DEFAULT}} values
 * will be replaced during code generation.
 */

#include "{{HEADER_NAME}}" // This will be replaced, e.g., "pid.h"
#include <math.h>          // For fabsf, INFINITY (if not defined in header)
#include <stddef.h>        // For NULL

// 定义浮点数后缀宏，根据DATA_TYPE选择
#ifdef __cplusplus
#define SFX_F {{SFX}}
#else
#define SFX_F {{SFX}}
#endif

#ifndef INFINITY
    /** @brief Definition of infinity if not already defined. */
    #define INFINITY (1.0f/0.0f)
#endif

/**
 * @brief Constrains a value within a specified minimum and maximum range.
 * @param[in] value The value to constrain.
 * @param[in] min_val   The minimum allowed value.
 * @param[in] max_val   The maximum allowed value.
 * @return The constrained value.
 */
static inline {{DATA_TYPE}} constrain_pid_output({{DATA_TYPE}} value, {{DATA_TYPE}} min_val, {{DATA_TYPE}} max_val) {
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}


/**
 * @brief Initializes the PID controller structure.
 * @see {{FUNCTION_PREFIX}}_Init in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_Init({{STRUCT_NAME}} *pid, {{DATA_TYPE}} Kp_continuous, {{DATA_TYPE}} Ki_continuous, {{DATA_TYPE}} Kd_continuous, {{DATA_TYPE}} sample_time_val) {
    if (pid == NULL) return;

    pid->Kp = Kp_continuous;
    // Ensure sample_time_val is positive to prevent division by zero or negative gains
    if (sample_time_val > 0.000001f) {
        pid->Ki = Ki_continuous * sample_time_val; // Convert continuous Ki to discrete
        pid->Kd = Kd_continuous / sample_time_val; // Convert continuous Kd to discrete
    } else {
        // Fallback if sample_time_val is invalid, though ideally an error should be flagged
        // In a real system, you might assert or return an error code.
        pid->Ki = Ki_continuous;
        pid->Kd = Kd_continuous;
    }
    pid->sample_time = (sample_time_val > 0.000001f) ? sample_time_val : 0.01f; // Default to 0.01 if invalid

    // Initialize ALL other members to library defaults specified by generator
    // These defaults are replaced by the Python generator based on UI settings
    pid->Kff = {{KFF_DEFAULT}};
    pid->ff_weight = {{FF_WEIGHT_DEFAULT}};

    pid->output_limit = {{OUTPUT_LIMIT_DEFAULT}};
    pid->integral_limit = {{INTEGRAL_LIMIT_DEFAULT}};
    pid->output_ramp = {{OUTPUT_RAMP_DEFAULT}};
    pid->deadband = {{DEADBAND_DEFAULT}};
    pid->integral_separation_threshold = {{INTEGRAL_SEPARATION_THRESHOLD_DEFAULT}};

    pid->d_filter_coef = {{D_FILTER_COEF_DEFAULT}};
    pid->input_filter_coef = {{INPUT_FILTER_COEF_DEFAULT}};
    pid->setpoint_filter_coef = {{SETPOINT_FILTER_COEF_DEFAULT}};

    // Initialize advanced features parameters
    pid->adaptive_enable = {{ADAPTIVE_ENABLE}};
    pid->adaptive_kp_min = {{ADAPTIVE_KP_MIN_DEFAULT}};
    pid->adaptive_kp_max = {{ADAPTIVE_KP_MAX_DEFAULT}};
    pid->adaptive_ki_min = {{ADAPTIVE_KI_MIN_DEFAULT}};
    pid->adaptive_ki_max = {{ADAPTIVE_KI_MAX_DEFAULT}};
    pid->adaptive_kd_min = {{ADAPTIVE_KD_MIN_DEFAULT}};
    pid->adaptive_kd_max = {{ADAPTIVE_KD_MAX_DEFAULT}};

    pid->fuzzy_enable = {{FUZZY_ENABLE}};
    pid->fuzzy_error_range = {{FUZZY_ERROR_RANGE_DEFAULT}};
    pid->fuzzy_derror_range = {{FUZZY_DERROR_RANGE_DEFAULT}};


    // Initialize state variables by calling Reset
    {{FUNCTION_PREFIX}}_Reset(pid);

    // Default operational modes
    pid->mode = PID_MODE_AUTOMATIC;
    pid->type = PID_TYPE_STANDARD;
    pid->work_mode = PID_MODE_POSITION;
}

/**
 * @brief Sets new PID tuning parameters.
 * @see {{FUNCTION_PREFIX}}_SetTunings in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetTunings({{STRUCT_NAME}} *pid, {{DATA_TYPE}} Kp_continuous, {{DATA_TYPE}} Ki_continuous, {{DATA_TYPE}} Kd_continuous) {
    if (pid == NULL) return;
    // Basic validation for gains: ensure they are non-negative
    if (Kp_continuous < 0.0f || Ki_continuous < 0.0f || Kd_continuous < 0.0f) return;

    pid->Kp = Kp_continuous;
    if (pid->sample_time > 0.000001f) {
        pid->Ki = Ki_continuous * pid->sample_time;
        pid->Kd = Kd_continuous / pid->sample_time;
    } else {
        // Fallback if sample_time is not properly set (should not happen if Init was called)
        pid->Ki = Ki_continuous;
        pid->Kd = Kd_continuous;
    }
}

/**
 * @brief Sets feedforward parameters.
 * @see {{FUNCTION_PREFIX}}_SetFeedForwardParams in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetFeedForwardParams({{STRUCT_NAME}} *pid, {{DATA_TYPE}} Kff, {{DATA_TYPE}} ff_weight) {
    if (pid == NULL) return;
    pid->Kff = Kff;
    pid->ff_weight = constrain_pid_output(ff_weight, 0.0f, 1.0f); // Weight should be between 0 and 1
}

/**
 * @brief Sets the controller sample time.
 * @see {{FUNCTION_PREFIX}}_SetSampleTime in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetSampleTime({{STRUCT_NAME}} *pid, {{DATA_TYPE}} sample_time_new) {
    if (pid == NULL || sample_time_new <= 0.000001f) return;

    // If sample time changes significantly, recalculate discrete Ki and Kd
    // This ensures that the continuous-domain behavior of Ki and Kd is preserved.
    if (pid->sample_time > 0.000001f && fabsf(pid->sample_time - sample_time_new) > 0.0000001f) {
        // Convert Ki and Kd back to continuous domain using old sample time
        {{DATA_TYPE}} ki_continuous = pid->Ki / pid->sample_time;
        {{DATA_TYPE}} kd_continuous = pid->Kd * pid->sample_time;
        // Convert to discrete domain using new sample time
        pid->Ki = ki_continuous * sample_time_new;
        pid->Kd = kd_continuous / sample_time_new;
    }
    pid->sample_time = sample_time_new;
}

/**
 * @brief Sets the absolute output limits.
 * @see {{FUNCTION_PREFIX}}_SetOutputLimits in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetOutputLimits({{STRUCT_NAME}} *pid, {{DATA_TYPE}} limit) {
    if (pid == NULL) return;
    pid->output_limit = fabsf(limit); // Store as positive, apply as +/- limit
}

/**
 * @brief Sets the absolute integral limits.
 * @see {{FUNCTION_PREFIX}}_SetIntegralLimits in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetIntegralLimits({{STRUCT_NAME}} *pid, {{DATA_TYPE}} limit) {
    if (pid == NULL) return;
    pid->integral_limit = fabsf(limit); // Store as positive
}

/**
 * @brief Sets the output ramp rate.
 * @see {{FUNCTION_PREFIX}}_SetOutputRamp in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetOutputRamp({{STRUCT_NAME}} *pid, {{DATA_TYPE}} rate) {
    if (pid == NULL) return;
    pid->output_ramp = fabsf(rate); // Rate is positive
}

/**
 * @brief Sets the error deadband.
 * @see {{FUNCTION_PREFIX}}_SetDeadband in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetDeadband({{STRUCT_NAME}} *pid, {{DATA_TYPE}} deadband_val) {
    if (pid == NULL) return;
    pid->deadband = fabsf(deadband_val);
}

/**
 * @brief Sets the integral separation threshold.
 * @see {{FUNCTION_PREFIX}}_SetIntegralSeparationThreshold in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetIntegralSeparationThreshold({{STRUCT_NAME}} *pid, {{DATA_TYPE}} threshold) {
    if (pid == NULL) return;
    pid->integral_separation_threshold = fabsf(threshold);
}

/**
 * @brief Sets the D-term filter coefficient.
 * @see {{FUNCTION_PREFIX}}_SetDFilter in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetDFilter({{STRUCT_NAME}} *pid, {{DATA_TYPE}} filter_coef) {
    if (pid == NULL) return;
    pid->d_filter_coef = constrain_pid_output(filter_coef, 0.0f, 1.0f);
}

/**
 * @brief Sets the input filter coefficient.
 * @see {{FUNCTION_PREFIX}}_SetInputFilter in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetInputFilter({{STRUCT_NAME}} *pid, {{DATA_TYPE}} filter_coef) {
    if (pid == NULL) return;
    pid->input_filter_coef = constrain_pid_output(filter_coef, 0.0f, 1.0f);
}

/**
 * @brief Sets the setpoint filter coefficient.
 * @see {{FUNCTION_PREFIX}}_SetSetpointFilter in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetSetpointFilter({{STRUCT_NAME}} *pid, {{DATA_TYPE}} filter_coef) {
    if (pid == NULL) return;
    pid->setpoint_filter_coef = constrain_pid_output(filter_coef, 0.0f, 1.0f);
}

/**
 * @brief Sets the PID controller mode.
 * @see {{FUNCTION_PREFIX}}_SetMode in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetMode({{STRUCT_NAME}} *pid, PID_ModeType mode) {
    if (pid == NULL) return;
    // Optional: Implement bumpless transfer logic if mode changes
    // For example, if switching from MANUAL to AUTOMATIC, adjust integral to match current output
    // This prevents a sudden "bump" in output when switching modes.
    // if (pid->mode == PID_MODE_MANUAL && mode == PID_MODE_AUTOMATIC && pid->Ki != 0.0f) {
    //    pid->integral = pid->output / pid->Ki; // Simplified, assumes output was from I-term mainly
    //    pid->integral = constrain_pid_output(pid->integral, -pid->integral_limit, pid->integral_limit);
    // }
    pid->mode = mode;
}

/**
 * @brief Sets the PID calculation type.
 * @see {{FUNCTION_PREFIX}}_SetType in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetType({{STRUCT_NAME}} *pid, PID_Type type) {
    if (pid == NULL) return;
    pid->type = type;
}

/**
 * @brief Sets the PID work mode (output type).
 * @see {{FUNCTION_PREFIX}}_SetWorkMode in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetWorkMode({{STRUCT_NAME}} *pid, PID_WorkMode work_mode) {
    if (pid == NULL) return;
    pid->work_mode = work_mode;
}

/**
 * @brief Enables or disables adaptive control.
 * @param[in,out] pid Pointer to the {{STRUCT_NAME}} instance.
 * @param[in]     enable True to enable, false to disable.
 */
void {{FUNCTION_PREFIX}}_SetAdaptiveEnable({{STRUCT_NAME}} *pid, bool enable) {
    if (pid == NULL) return;
    pid->adaptive_enable = enable;
}

/**
 * @brief Sets adaptive Kp limits.
 * @param[in,out] pid Pointer to the {{STRUCT_NAME}} instance.
 * @param[in]     min_val Minimum Kp.
 * @param[in]     max_val Maximum Kp.
 */
void {{FUNCTION_PREFIX}}_SetAdaptiveKpLimits({{STRUCT_NAME}} *pid, {{DATA_TYPE}} min_val, {{DATA_TYPE}} max_val) {
    if (pid == NULL) return;
    pid->adaptive_kp_min = min_val;
    pid->adaptive_kp_max = max_val;
}

/**
 * @brief Sets adaptive Ki limits.
 * @param[in,out] pid Pointer to the {{STRUCT_NAME}} instance.
 * @param[in]     min_val Minimum Ki.
 * @param[in]     max_val Maximum Ki.
 */
void {{FUNCTION_PREFIX}}_SetAdaptiveKiLimits({{STRUCT_NAME}} *pid, {{DATA_TYPE}} min_val, {{DATA_TYPE}} max_val) {
    if (pid == NULL) return;
    pid->adaptive_ki_min = min_val;
    pid->adaptive_ki_max = max_val;
}

/**
 * @brief Sets adaptive Kd limits.
 * @param[in,out] pid Pointer to the {{STRUCT_NAME}} instance.
 * @param[in]     min_val Minimum Kd.
 * @param[in]     max_val Maximum Kd.
 */
void {{FUNCTION_PREFIX}}_SetAdaptiveKdLimits({{STRUCT_NAME}} *pid, {{DATA_TYPE}} min_val, {{DATA_TYPE}} max_val) {
    if (pid == NULL) return;
    pid->adaptive_kd_min = min_val;
    pid->adaptive_kd_max = max_val;
}

/**
 * @brief Enables or disables fuzzy PID control.
 * @param[in,out] pid Pointer to the {{STRUCT_NAME}} instance.
 * @param[in]     enable True to enable, false to disable.
 */
void {{FUNCTION_PREFIX}}_SetFuzzyEnable({{STRUCT_NAME}} *pid, bool enable) {
    if (pid == NULL) return;
    pid->fuzzy_enable = enable;
}

/**
 * @brief Sets fuzzy error and derivative error ranges.
 * @param[in,out] pid Pointer to the {{STRUCT_NAME}} instance.
 * @param[in]     error_range Range for fuzzy error input.
 * @param[in]     derror_range Range for fuzzy derivative error input.
 */
void {{FUNCTION_PREFIX}}_SetFuzzyRanges({{STRUCT_NAME}} *pid, {{DATA_TYPE}} error_range, {{DATA_TYPE}} derror_range) {
    if (pid == NULL) return;
    pid->fuzzy_error_range = fabsf(error_range);
    pid->fuzzy_derror_range = fabsf(derror_range);
}


/**
 * @brief Computes the PID output.
 * @see {{FUNCTION_PREFIX}}_Compute in {{HEADER_NAME}} for detailed parameter descriptions.
 */
{{DATA_TYPE}} {{FUNCTION_PREFIX}}_Compute({{STRUCT_NAME}} *pid, {{DATA_TYPE}} setpoint, {{DATA_TYPE}} measure) {
    if (pid == NULL) return 0.0f; // Or some error code/value
    if (pid->sample_time <= 0.000001f) return pid->output; // Avoid division by zero if sample time is invalid

    // If in manual mode, return the manually set output
    if (pid->mode == PID_MODE_MANUAL) {
        return pid->output;
    }

    // Apply input filtering to measurement
    if (pid->input_filter_coef > 0.0f && pid->input_filter_coef < 1.0f) {
        pid->filtered_measure = pid->filtered_measure * (1.0f - pid->input_filter_coef) +
                                measure * pid->input_filter_coef;
        measure = pid->filtered_measure; // Use filtered measurement for calculations
    } else {
        pid->filtered_measure = measure; // No filtering or invalid coefficient
    }

    // Apply setpoint filtering
    if (pid->setpoint_filter_coef > 0.0f && pid->setpoint_filter_coef < 1.0f) {
        pid->filtered_setpoint = pid->filtered_setpoint * (1.0f - pid->setpoint_filter_coef) +
                                 setpoint * pid->setpoint_filter_coef;
        setpoint = pid->filtered_setpoint; // Use filtered setpoint
    } else {
        pid->filtered_setpoint = setpoint;
    }

    // Calculate error
    {{DATA_TYPE}} error = setpoint - measure;

    // Apply deadband: if error is within deadband, treat as zero
    if (pid->deadband > 0.0f && fabsf(error) < pid->deadband) {
        error = 0.0f;
    }

    // --- Proportional Term ---
    {{DATA_TYPE}} p_term;
    if (pid->type == PID_TYPE_STANDARD || pid->type == PID_TYPE_PI_D) {
        p_term = pid->Kp * error; // P on Error
    } else { // PID_TYPE_I_PD
        // For I-PD, P-term is typically based on measurement change or absolute measurement.
        // Here, we use P on absolute measurement (negative for stability in common control loops).
        // This specific interpretation of I-PD's P-term is based on some industrial controllers
        // where P and D act on the process variable directly.
        // If P-term should be based on error for I-PD, change this line to: p_term = pid->Kp * error;
        p_term = -pid->Kp * measure; // P on Measurement (negative contribution)
    }
    pid->last_p_term = p_term; // Store for debugging

    // --- Integral Term ---
    // Integral action only if error is below separation threshold (integral separation)
    if (fabsf(error) < pid->integral_separation_threshold) {
        pid->integral += pid->Ki * error;
        // Anti-windup: Clamp integral term
        pid->integral = constrain_pid_output(pid->integral, -pid->integral_limit, pid->integral_limit);
    }
    pid->last_i_term = pid->integral; // Store for debugging

    // --- Derivative Term ---
    {{DATA_TYPE}} derivative_input;
    if (pid->type == PID_TYPE_STANDARD) {
        derivative_input = (error - pid->prev_error); // D on Error
    } else { // PID_TYPE_PI_D or PID_TYPE_I_PD
        derivative_input = -(measure - pid->prev_measure); // D on Measurement (negative due to (pv-pv_prev))
    }
    derivative_input /= pid->sample_time;

    // Apply derivative low-pass filter
    if (pid->d_filter_coef > 0.0f && pid->d_filter_coef < 1.0f) {
        pid->filtered_d = pid->filtered_d * (1.0f - pid->d_filter_coef) +
                          derivative_input * pid->d_filter_coef;
    } else {
        pid->filtered_d = derivative_input; // No filtering or invalid coefficient
    }
    {{DATA_TYPE}} d_term = pid->Kd * pid->filtered_d;
    pid->last_d_term = d_term; // Store for debugging

    // --- Feedforward Term ---
    // Typically, feedforward is based on the setpoint
    pid->last_ff_term = pid->Kff * setpoint * pid->ff_weight;

    // --- Total Output Calculation ---
    {{DATA_TYPE}} computed_output = p_term + pid->integral + d_term + pid->last_ff_term;

    // --- Advanced Features (Conceptual - User needs to implement logic) ---
    // These are placeholders. Actual adaptive/fuzzy logic would modify Kp, Ki, Kd
    // or directly influence the computed_output based on error, d_error, etc.
    #if {{ADAPTIVE_ENABLE}}
    if (pid->adaptive_enable) {
        // Example: Simple adaptive Kp based on error magnitude
        // This is a conceptual placeholder. Real adaptive logic is complex.
        // if (fabsf(error) > 10.0f) {
        //    pid->Kp = constrain_pid_output(pid->Kp * 1.1f, pid->adaptive_kp_min, pid->adaptive_kp_max);
        // } else {
        //    pid->Kp = constrain_pid_output(pid->Kp * 0.9f, pid->adaptive_kp_min, pid->adaptive_kp_max);
        // }
        // For a more robust implementation, consider a separate function:
        // {{FUNCTION_PREFIX}}_UpdateAdaptiveGains(pid, error, derivative_input);
    }
    #endif

    #if {{FUZZY_ENABLE}}
    if (pid->fuzzy_enable) {
        // Example: Fuzzy logic to fine-tune output or gains
        // This is a conceptual placeholder. Real fuzzy logic involves membership functions,
        // rule bases, and defuzzification.
        // {{DATA_TYPE}} fuzzy_correction = {{FUNCTION_PREFIX}}_CalculateFuzzyCorrection(pid, error, derivative_input);
        // computed_output += fuzzy_correction;
    }
    #endif

    // --- Apply output rate limiting (ramp control) ---
    if (pid->output_ramp > 0.0f) {
        {{DATA_TYPE}} max_change_this_cycle = pid->output_ramp * pid->sample_time;
        {{DATA_TYPE}} change_in_output = computed_output - pid->prev_output; // prev_output is actual previous output

        // Clamp the change within the allowed ramp rate
        change_in_output = constrain_pid_output(change_in_output, -max_change_this_cycle, max_change_this_cycle);
        computed_output = pid->prev_output + change_in_output;
    }

    // Apply output saturation (final clamping)
    computed_output = constrain_pid_output(computed_output, -pid->output_limit, pid->output_limit);

    // --- Update State for Next Iteration ---
    pid->prev_error = error;
    pid->prev_measure = measure; // Store the (possibly filtered) measurement used
    pid->prev_setpoint = setpoint; // Store the (possibly filtered) setpoint used

    // Handle velocity mode output
    if (pid->work_mode == PID_MODE_VELOCITY) {
        // In velocity mode, the output is the increment to the control variable.
        // The `pid->output` stores the *change* in output, and `pid->prev_output`
        // accumulates the absolute output for ramp limiting in the next cycle.
        pid->output = computed_output - pid->prev_output; // Output is the increment
        pid->prev_output = computed_output; // Update prev_output to the new absolute level
    } else { // PID_MODE_POSITION
        // In positional mode, the output is the absolute control variable.
        pid->output = computed_output;
        pid->prev_output = computed_output; // prev_output tracks the actual output for ramp limiting
    }

    return pid->output;
}

/**
 * @brief Computes PID output with dynamic sample time based on current time.
 * @see {{FUNCTION_PREFIX}}_ComputeWithTime in {{HEADER_NAME}} for detailed parameter descriptions.
 */
{{DATA_TYPE}} {{FUNCTION_PREFIX}}_ComputeWithTime({{STRUCT_NAME}} *pid, {{DATA_TYPE}} setpoint, {{DATA_TYPE}} measure, uint32_t current_time_ms) {
    if (pid == NULL) return 0.0f;

    // Handle first call after Init/Reset
    if (pid->last_time == 0) {
        pid->last_time = current_time_ms;
        // Initialize prev_measure, prev_error, filtered values for the first computation
        pid->prev_measure = measure;
        pid->prev_error = setpoint - measure;
        pid->filtered_measure = measure;
        pid->filtered_setpoint = setpoint;
        // For the very first call, we might not want to compute a full PID output
        // as delta_time would be zero or undefined.
        // A common approach is to return 0 or the initial output, and then compute
        // normally on subsequent calls.
        // For simplicity, we will proceed with computation, but dt_seconds will be 0.
        // The _Compute function handles dt_seconds <= 0.000001f by returning prev output.
    }

    uint32_t elapsed_ms = current_time_ms - pid->last_time;
    {{DATA_TYPE}} dt_seconds = ({{DATA_TYPE}})elapsed_ms / 1000.0f;

    // If no time elapsed or very small time, return previous output to prevent division by zero
    // and avoid erratic behavior.
    if (dt_seconds <= 0.000001f) {
         return pid->output;
    }

    // Store original discrete Ki, Kd, and sample_time
    // We need to convert back to continuous gains, then re-discretize with the new dt.
    {{DATA_TYPE}} original_Ki_discrete = pid->Ki;
    {{DATA_TYPE}} original_Kd_discrete = pid->Kd;
    {{DATA_TYPE}} original_sample_time = pid->sample_time;

    // Convert current discrete gains back to continuous domain
    {{DATA_TYPE}} ki_continuous = original_Ki_discrete / original_sample_time;
    {{DATA_TYPE}} kd_continuous = original_Kd_discrete * original_sample_time;

    // Temporarily adjust discrete gains for this specific delta_time
    pid->Ki = ki_continuous * dt_seconds;
    pid->Kd = kd_continuous / dt_seconds;
    pid->sample_time = dt_seconds; // Temporarily set sample_time for _Compute

    {{DATA_TYPE}} result = {{FUNCTION_PREFIX}}_Compute(pid, setpoint, measure);

    // Restore original discrete gains and sample_time for subsequent fixed-interval calls or SetTunings
    pid->Ki = original_Ki_discrete;
    pid->Kd = original_Kd_discrete;
    pid->sample_time = original_sample_time;

    pid->last_time = current_time_ms;

    return result;
}


/**
 * @brief Resets the PID controller's internal state.
 * @see {{FUNCTION_PREFIX}}_Reset in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_Reset({{STRUCT_NAME}} *pid) {
    if (pid == NULL) return;

    pid->integral         = 0.0f;
    pid->prev_error       = 0.0f;
    pid->prev_prev_error  = 0.0f; // Reset if used by specific logic
    pid->prev_measure     = 0.0f; // Or initialize to current measurement if available
    pid->prev_prev_measure= 0.0f; // Reset if used
    pid->prev_output      = 0.0f;
    pid->prev_setpoint    = 0.0f; // Or initialize to current setpoint if available

    pid->filtered_d       = 0.0f;
    pid->filtered_measure = 0.0f; // Reset filtered values
    pid->filtered_setpoint= 0.0f;

    pid->output           = 0.0f; // Current output reset

    pid->last_time        = 0;    // Reset for ComputeWithTime to trigger first-call logic

    // Debug terms
    pid->last_p_term      = 0.0f;
    pid->last_i_term      = 0.0f; // Reset last integral term
    pid->last_d_term      = 0.0f; // Reset last derivative term
    pid->last_ff_term     = 0.0f;
}

/**
 * @brief Manually sets the PID output value.
 * @see {{FUNCTION_PREFIX}}_SetOutput in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_SetOutput({{STRUCT_NAME}} *pid, {{DATA_TYPE}} output_val) {
    if (pid == NULL) return;
    // This function should only take effect if in manual mode
    if (pid->mode == PID_MODE_MANUAL) {
        pid->output = constrain_pid_output(output_val, -pid->output_limit, pid->output_limit);
        // When output is set manually, prev_output should also reflect this for ramp limiting if mode changes
        pid->prev_output = pid->output;
    }
}

/**
 * @brief Retrieves the last computed PID components.
 * @see {{FUNCTION_PREFIX}}_GetComponents in {{HEADER_NAME}} for detailed parameter descriptions.
 */
void {{FUNCTION_PREFIX}}_GetComponents({{STRUCT_NAME}} *pid, {{DATA_TYPE}} *p_term, {{DATA_TYPE}} *i_term, {{DATA_TYPE}} *d_term, {{DATA_TYPE}} *ff_term) {
    if (pid == NULL) return;

    if (p_term != NULL) {
        *p_term = pid->last_p_term;
    }
    if (i_term != NULL) {
        *i_term = pid->integral; // Current integral value
    }
    if (d_term != NULL) {
        // d_term is typically Kd * filtered_derivative_input. pid->filtered_d stores the derivative_input after filtering.
        // So, the actual d_term would be pid->Kd * pid->filtered_d
        *d_term = pid->Kd * pid->filtered_d;
    }
    if (ff_term != NULL) {
        *ff_term = pid->last_ff_term;
    }
}
