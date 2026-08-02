from pathlib import Path

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')

state_anchor = '''    static std::atomic<uint64_t> s_v71_last_logged_pass = 0;
'''
state_add = state_anchor + '''    static std::mutex s_v72_chain_mutex;
    static bool s_v72_chain_seeded = false;
    static bool s_v72_chain_complete = false;
    static UINT s_v72_chain_depth = 0;
    static void *s_v72_seed_pipeline_state = nullptr;
    static std::vector<uint64_t> s_v72_chain_frontier;
    static std::atomic<uint64_t> s_v72_seed_count = 0;
    static std::atomic<uint64_t> s_v72_pass_count = 0;
    static std::atomic<uint64_t> s_v72_feedback_count = 0;
    static std::atomic<uint64_t> s_v72_result_count = 0;
'''

proto_anchor = '''    bool v71_reset_history_feedback_before_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''
proto_add = proto_anchor + '''    void v72_observe_post_feedback_event(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        bool graphics,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''

active_old = '''\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX temporal feedback reset visual candidate v71: ACTIVE target=v70-first-feedback-boundary identification=logical-root0-uav-offsets12,13 signature=dispatch-8x8 clear=zero-before-dispatch clear-both-feedback-uavs=enabled resource-copies=disabled explicit-resource-barriers=disabled commands_modified=1.");
'''
active_new = '''\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX temporal feedback reset visual candidate v71: DORMANT superseded_by=v72 commands_modified=0.");
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX post-feedback lighting chain v72: ACTIVE source=v70-feedback-nonfeedback-outputs root0-offsets14,15 max-depth=5 skip-seed-pipeline=enabled ignore-inplace-feedback=enabled readback=disabled resource-copies=disabled resource-barriers=disabled commands_modified=0.");
'''

impl_anchor = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
'''
impl = r'''    bool v72_contains_resource_id(
        const std::vector<uint64_t> &values,
        uint64_t resource_id)
    {
        return resource_id != 0 &&
            std::find(values.begin(), values.end(), resource_id) != values.end();
    }

    bool v72_input_contains_resource(
        const std::vector<v70_input_reference> &inputs,
        uint64_t resource_id)
    {
        for (const auto &input : inputs)
            if (input.resource_id == resource_id)
                return true;
        return false;
    }

    void v72_log_pass(
        UINT depth,
        const char *kind,
        void *pipeline_state,
        const std::vector<v70_input_reference> &inputs,
        const std::vector<v66_output_candidate> &outputs,
        const std::vector<uint64_t> &next_frontier,
        uint64_t feedback_count,
        UINT group_x,
        UINT group_y,
        UINT group_z)
    {
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX post-feedback lighting chain v72: POST_FEEDBACK_CHAIN_PASS depth=%u event_kind=%s pipeline_state=%p input_count=%zu output_count=%zu next_frontier_count=%zu feedback_count=%llu groups=%u,%u,%u commands_modified=0.",
            depth,
            kind != nullptr ? kind : "unknown",
            pipeline_state,
            inputs.size(),
            outputs.size(),
            next_frontier.size(),
            static_cast<unsigned long long>(feedback_count),
            group_x, group_y, group_z);
        for (UINT index = 0; index < inputs.size(); ++index)
        {
            const auto &input = inputs[index];
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX post-feedback lighting chain v72: POST_FEEDBACK_INPUT depth=%u input_index=%u resource_id=%llu descriptor_kind=%s binding_kind=%s root_parameter=%u descriptor_offset=%u.",
                depth, index,
                static_cast<unsigned long long>(input.resource_id),
                v55_descriptor_kind_name(input.descriptor_kind),
                input.binding_kind == 2 ? "direct-root" : "table",
                input.root_parameter,
                input.descriptor_offset);
        }
        for (UINT index = 0; index < outputs.size(); ++index)
        {
            const auto &output = outputs[index];
            const bool in_place = v72_input_contains_resource(inputs, output.resource_id);
            const bool carried = v72_contains_resource_id(next_frontier, output.resource_id);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX post-feedback lighting chain v72: POST_FEEDBACK_OUTPUT depth=%u output_index=%u resource_id=%llu format=%u dimension=%u width=%llu height=%u flags=0x%X binding_kind=%s root_parameter=%u descriptor_offset=%u in_place_feedback=%u carried_forward=%u.",
                depth, index,
                static_cast<unsigned long long>(output.resource_id),
                output.format,
                output.dimension,
                static_cast<unsigned long long>(output.width),
                output.height,
                output.flags,
                output.binding_kind == 2 ? "direct-root-uav" : "table-uav",
                output.root_parameter,
                output.descriptor_offset,
                in_place ? 1u : 0u,
                carried ? 1u : 0u);
        }
    }

    void v72_finish_chain(const char *termination)
    {
        bool should_log = false;
        UINT depth = 0;
        {
            std::lock_guard<std::mutex> lock(s_v72_chain_mutex);
            if (!s_v72_chain_complete)
            {
                s_v72_chain_complete = true;
                should_log = true;
                depth = s_v72_chain_depth;
            }
        }
        if (!should_log)
            return;
        s_v72_result_count.fetch_add(1, std::memory_order_acq_rel);
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX post-feedback lighting chain v72: POST_FEEDBACK_CHAIN_RESULT success=1 steps=%u termination=%s seed_offsets=14,15 feedback_clearing=disabled commands_modified=0.",
            depth,
            termination != nullptr ? termination : "unknown");
    }

    void v72_observe_post_feedback_event(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        bool graphics,
        UINT group_x,
        UINT group_y,
        UINT group_z)
    {
        if (command_list == nullptr ||
            !s_v66_world_consumer_found.load(std::memory_order_acquire))
            return;

        v66_command_binding_state state = {};
        {
            std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
            const auto found = s_v66_binding_states.find(command_list);
            if (found == s_v66_binding_states.end())
                return;
            state = found->second;
        }

        bool seeded = false;
        {
            std::lock_guard<std::mutex> lock(s_v72_chain_mutex);
            seeded = s_v72_chain_seeded;
        }
        if (!seeded && !graphics)
        {
            v71_resolved_uav feedback_a = {};
            v71_resolved_uav feedback_b = {};
            v71_resolved_uav current_output = {};
            v71_resolved_uav aux_output = {};
            if (!v71_history_signature_matches(
                    state, group_x, group_y, group_z,
                    feedback_a, feedback_b, current_output, aux_output))
                return;

            bool created = false;
            {
                std::lock_guard<std::mutex> lock(s_v72_chain_mutex);
                if (!s_v72_chain_seeded)
                {
                    s_v72_chain_seeded = true;
                    s_v72_chain_complete = false;
                    s_v72_chain_depth = 0;
                    s_v72_seed_pipeline_state = state.pipeline_state;
                    s_v72_chain_frontier.clear();
                    if (current_output.resource.resource_id != 0)
                        s_v72_chain_frontier.push_back(current_output.resource.resource_id);
                    if (aux_output.resource.resource_id != 0 &&
                        aux_output.resource.resource_id != current_output.resource.resource_id)
                        s_v72_chain_frontier.push_back(aux_output.resource.resource_id);
                    created = !s_v72_chain_frontier.empty();
                }
            }
            if (created)
            {
                s_v72_seed_count.fetch_add(1, std::memory_order_acq_rel);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX post-feedback lighting chain v72: POST_FEEDBACK_CHAIN_SEED pipeline_state=%p source_offsets=14,15 current_output_resource=%llu aux_output_resource=%llu dimensions=%llux%u max_depth=5 commands_modified=0.",
                    state.pipeline_state,
                    static_cast<unsigned long long>(current_output.resource.resource_id),
                    static_cast<unsigned long long>(aux_output.resource.resource_id),
                    static_cast<unsigned long long>(current_output.resource.width),
                    current_output.resource.height);
            }
            return;
        }

        std::vector<uint64_t> frontier;
        UINT expected_depth = 0;
        void *seed_pipeline = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v72_chain_mutex);
            if (!s_v72_chain_seeded || s_v72_chain_complete ||
                s_v72_chain_frontier.empty())
                return;
            frontier = s_v72_chain_frontier;
            expected_depth = s_v72_chain_depth;
            seed_pipeline = s_v72_seed_pipeline_state;
        }

        if (state.pipeline_state == seed_pipeline)
            return;

        std::vector<v70_input_reference> inputs;
        std::vector<v66_output_candidate> outputs;
        if (!v70_scan_chain_bindings(
                state, graphics, frontier, inputs, outputs) ||
            outputs.empty())
            return;

        const uint64_t feedback = v70_feedback_count(inputs, outputs);
        std::vector<uint64_t> next_frontier;
        for (const auto &output : outputs)
        {
            if (output.resource_id == 0 ||
                v72_input_contains_resource(inputs, output.resource_id))
                continue;
            if (!v72_contains_resource_id(next_frontier, output.resource_id))
                next_frontier.push_back(output.resource_id);
        }

        const UINT depth = expected_depth + 1;
        bool accepted = false;
        {
            std::lock_guard<std::mutex> lock(s_v72_chain_mutex);
            if (s_v72_chain_seeded && !s_v72_chain_complete &&
                s_v72_chain_depth == expected_depth)
            {
                s_v72_chain_depth = depth;
                s_v72_chain_frontier = next_frontier;
                accepted = true;
            }
        }
        if (!accepted)
            return;

        s_v72_pass_count.fetch_add(1, std::memory_order_acq_rel);
        if (feedback != 0)
            s_v72_feedback_count.fetch_add(feedback, std::memory_order_acq_rel);
        v72_log_pass(
            depth, kind, state.pipeline_state,
            inputs, outputs, next_frontier, feedback,
            group_x, group_y, group_z);

        if (next_frontier.empty())
            v72_finish_chain("no-nonfeedback-output");
        else if (depth >= 5)
            v72_finish_chain("depth-limit");
    }

'''

old_dispatch = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x, UINT group_y, UINT group_z)
    {
        v71_reset_history_feedback_before_dispatch(
            command_list, group_x, group_y, group_z);
        if (s_v66_original_dispatch != nullptr)
            s_v66_original_dispatch(command_list, group_x, group_y, group_z);
        v70_observe_chain_event(
            command_list, "direct-compute", false,
            group_x, group_y, group_z);
        v66_observe_consumer_dispatch(
            command_list, "direct-compute", group_x, group_y, group_z);
    }
'''
new_dispatch = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x, UINT group_y, UINT group_z)
    {
        if (s_v66_original_dispatch != nullptr)
            s_v66_original_dispatch(command_list, group_x, group_y, group_z);
        v72_observe_post_feedback_event(
            command_list, "direct-compute", false,
            group_x, group_y, group_z);
        v70_observe_chain_event(
            command_list, "direct-compute", false,
            group_x, group_y, group_z);
        v66_observe_consumer_dispatch(
            command_list, "direct-compute", group_x, group_y, group_z);
    }
'''

old_execute = '''        else if (dispatch_compute)
        {
            v70_observe_chain_event(
                command_list,
                "execute-indirect-compute",
                false,
                max_command_count, 0, 0);
'''
new_execute = '''        else if (dispatch_compute)
        {
            v72_observe_post_feedback_event(
                command_list,
                "execute-indirect-compute",
                false,
                max_command_count, 0, 0);
            v70_observe_chain_event(
                command_list,
                "execute-indirect-compute",
                false,
                max_command_count, 0, 0);
'''

old_draw1 = '''        v70_observe_chain_event(
            command_list, "draw-instanced", true,
            vertex_count, instance_count, 0);
'''
new_draw1 = '''        v72_observe_post_feedback_event(
            command_list, "draw-instanced", true,
            vertex_count, instance_count, 0);
        v70_observe_chain_event(
            command_list, "draw-instanced", true,
            vertex_count, instance_count, 0);
'''

old_draw2 = '''        v70_observe_chain_event(
            command_list, "draw-indexed-instanced", true,
            index_count, instance_count, 0);
'''
new_draw2 = '''        v72_observe_post_feedback_event(
            command_list, "draw-indexed-instanced", true,
            index_count, instance_count, 0);
        v70_observe_chain_event(
            command_list, "draw-indexed-instanced", true,
            index_count, instance_count, 0);
'''

if 'D3DMetal RTX post-feedback lighting chain v72: ACTIVE' not in text:
    replacements = [
        ('state', state_anchor, state_add),
        ('prototype', proto_anchor, proto_add),
        ('active marker', active_old, active_new),
        ('implementation', impl_anchor, impl + impl_anchor),
        ('dispatch hook', old_dispatch, new_dispatch),
        ('execute-indirect hook', old_execute, new_execute),
        ('draw-instanced hook', old_draw1, new_draw1),
        ('draw-indexed hook', old_draw2, new_draw2),
    ]
    for label, old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f'ERROR: {label} anchor count {count}, expected 1')
        text = text.replace(old, new, 1)
else:
    print('V72_PATCH_ALREADY_APPLIED=YES')

source.write_text(text, encoding='utf-8')
Path('v72-patch-report.txt').write_text(
    '\n'.join([
        'V72_POST_FEEDBACK_LIGHTING_CHAIN_PATCH_OK',
        'SOURCE=V70_FIRST_FEEDBACK_BOUNDARY_NONFEEDBACK_OUTPUTS',
        'SEED_DESCRIPTOR_OFFSETS=14,15',
        'MAX_DEPTH=5',
        'SEED_PIPELINE_SKIPPED=YES',
        'INPLACE_FEEDBACK_EXCLUDED_FROM_FRONTIER=YES',
        'V71_FEEDBACK_CLEARING=DISABLED',
        'GPU_READBACK=DISABLED',
        'RESOURCE_COPIES=DISABLED',
        'RESOURCE_BARRIERS=DISABLED',
        'COMMANDS_MODIFIED=NO',
        'RESULT=PASS',
    ]) + '\n', encoding='ascii')
print('V72_POST_FEEDBACK_LIGHTING_CHAIN_PATCH_OK')
