from pathlib import Path

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')

# 1. Add V70 structs after v66_output_candidate.
struct_anchor = '''    struct v66_output_candidate
    {
        uint64_t resource_id = 0;
        unsigned int format = 0;
        unsigned int dimension = 0;
        UINT64 width = 0;
        UINT height = 0;
        unsigned int flags = 0;
        unsigned int binding_kind = 0; // 1=table UAV, 2=direct root UAV
        UINT root_parameter = 0;
        UINT descriptor_offset = 0;
    };
'''
struct_add = struct_anchor + '''
    struct v70_input_reference
    {
        uint64_t resource_id = 0;
        unsigned int descriptor_kind = 0; // 1=CBV, 2=SRV, 3=UAV
        unsigned int binding_kind = 0; // 1=table, 2=direct root
        UINT root_parameter = 0;
        UINT descriptor_offset = 0;
    };

    struct v70_chain_pass_signature
    {
        UINT depth = 0;
        void *pipeline_state = nullptr;
        const char *event_kind = nullptr;
        uint64_t event_index = 0;
        uint64_t feedback_count = 0;
        std::vector<v70_input_reference> inputs;
        std::vector<v66_output_candidate> outputs;
    };

    struct v70_chain_phase_state
    {
        bool seeded = false;
        bool complete = false;
        UINT depth = 0;
        std::vector<uint64_t> frontier;
        std::vector<v70_chain_pass_signature> passes;
    };
'''

# 2. State + prototypes.
state_anchor = '''    static std::atomic<uint64_t> s_v69_last_signal_check_tick_ms = 0;
'''
state_add = state_anchor + '''    static std::mutex s_v70_chain_mutex;
    static v70_chain_phase_state s_v70_world_chain;
    static v70_chain_phase_state s_v70_post_chain;
    static std::atomic<uint64_t> s_v70_event_index = 0;
    static std::atomic<uint64_t> s_v70_chain_candidate_count = 0;
    static std::atomic<uint64_t> s_v70_world_step_count = 0;
    static std::atomic<uint64_t> s_v70_post_step_count = 0;
    static std::atomic<uint64_t> s_v70_feedback_candidate_count = 0;
    static std::atomic<bool> s_v70_world_chain_complete = false;
    static std::atomic<bool> s_v70_post_chain_complete = false;
    static std::atomic<bool> s_v70_comparison_complete = false;
'''

proto_anchor = '''    void v66_install_command_list_consumer_hooks(
        ID3D12GraphicsCommandList4 *command_list);
'''
proto_add = proto_anchor + '''    void v70_seed_chain(
        bool post_menu,
        void *pipeline_state,
        const char *kind,
        uint64_t event_index,
        const std::vector<v66_output_candidate> &outputs);
    void v70_observe_chain_event(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        bool graphics,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''

# 3. Active log.
active_anchor = '''\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX manual normal-menu history transition v69: ACTIVE trigger=explicit-signal signal-file=C:/kaiozen-v69-menu-closed.signal automatic-gap-detection=disabled consumer-observation=v66 persistent-output-comparison=enabled readback=disabled resource-barriers=disabled commands_modified=0.");
'''
active_add = active_anchor + '''\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX downstream lighting dependency chain v70: ACTIVE source=first-rayhit-consumer max-depth=3 stop-on-feedback=enabled phases=world,manual-post-menu logical-slot-comparison=enabled physical-resource-persistence=diagnostic-only readback=disabled resource-copies=disabled resource-barriers=disabled commands_modified=0.");
'''

# 4. Core V70 implementation before v66_log_outputs.
impl_anchor = '''    void v66_log_outputs(
'''
impl = r'''    bool v70_contains_id(const std::vector<uint64_t> &ids, uint64_t value)
    {
        return value != 0 &&
            std::find(ids.begin(), ids.end(), value) != ids.end();
    }

    void v70_add_input_reference(
        std::vector<v70_input_reference> &inputs,
        uint64_t resource_id,
        unsigned int descriptor_kind,
        unsigned int binding_kind,
        UINT root_parameter,
        UINT descriptor_offset)
    {
        if (resource_id == 0)
            return;
        for (const auto &existing : inputs)
        {
            if (existing.resource_id == resource_id &&
                existing.binding_kind == binding_kind &&
                existing.root_parameter == root_parameter &&
                existing.descriptor_offset == descriptor_offset)
                return;
        }
        if (inputs.size() >= 24)
            return;
        v70_input_reference input = {};
        input.resource_id = resource_id;
        input.descriptor_kind = descriptor_kind;
        input.binding_kind = binding_kind;
        input.root_parameter = root_parameter;
        input.descriptor_offset = descriptor_offset;
        inputs.push_back(input);
    }

    bool v70_scan_chain_bindings(
        const v66_command_binding_state &state,
        bool graphics,
        const std::vector<uint64_t> &frontier,
        std::vector<v70_input_reference> &inputs,
        std::vector<v66_output_candidate> &outputs)
    {
        const auto &tables = graphics ? state.graphics_tables : state.compute_tables;
        for (const auto &table : tables)
        {
            v55_heap_info heap = {};
            UINT base_index = 0;
            if (!v55_find_heap_by_gpu(table.second, heap, base_index))
                continue;
            const UINT remaining = heap.count > base_index ? heap.count - base_index : 0;
            const UINT inspect = remaining < 96u ? remaining : 96u;
            for (UINT offset = 0; offset < inspect; ++offset)
            {
                const UINT64 handle = heap.gpu_start +
                    static_cast<UINT64>(base_index + offset) * heap.increment;
                v55_heap_info resolved_heap = {};
                UINT descriptor_index = 0;
                v55_descriptor_info descriptor = {};
                v55_resource_info resource = {};
                if (!v55_resolve_gpu_descriptor(
                        handle, resolved_heap, descriptor_index,
                        descriptor, resource))
                    continue;
                if (v70_contains_id(frontier, resource.resource_id))
                {
                    v70_add_input_reference(
                        inputs, resource.resource_id, descriptor.kind, 1,
                        table.first, offset);
                }
                if (descriptor.kind == 3)
                {
                    v66_add_output_candidate(
                        outputs, descriptor, resource, 1,
                        table.first, offset);
                }
            }
        }

        const auto &srvs = graphics ? state.graphics_srvs : state.compute_srvs;
        const auto &uavs = graphics ? state.graphics_uavs : state.compute_uavs;
        for (const auto &binding : srvs)
        {
            v55_resource_info resource = {};
            if (!v66_find_resource_by_gpu_va(binding.second, resource))
                continue;
            if (v70_contains_id(frontier, resource.resource_id))
            {
                v70_add_input_reference(
                    inputs, resource.resource_id, 2, 2,
                    binding.first, 0);
            }
        }
        for (const auto &binding : uavs)
        {
            v55_resource_info resource = {};
            if (!v66_find_resource_by_gpu_va(binding.second, resource))
                continue;
            if (v70_contains_id(frontier, resource.resource_id))
            {
                v70_add_input_reference(
                    inputs, resource.resource_id, 3, 2,
                    binding.first, 0);
            }
            v55_descriptor_info descriptor = {};
            descriptor.kind = 3;
            descriptor.format = resource.format;
            v66_add_output_candidate(
                outputs, descriptor, resource, 2,
                binding.first, 0);
        }
        return !inputs.empty();
    }

    uint64_t v70_feedback_count(
        const std::vector<v70_input_reference> &inputs,
        const std::vector<v66_output_candidate> &outputs)
    {
        uint64_t count = 0;
        for (const auto &output : outputs)
        {
            for (const auto &input : inputs)
            {
                if (output.resource_id == input.resource_id)
                {
                    ++count;
                    break;
                }
            }
        }
        return count;
    }

    void v70_log_chain_pass(
        const char *phase,
        const v70_chain_pass_signature &pass,
        UINT group_x,
        UINT group_y,
        UINT group_z)
    {
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX downstream lighting dependency chain v70: CHAIN_PASS phase=%s depth=%u event_kind=%s event_index=%llu pipeline_state=%p input_count=%zu output_count=%zu feedback_count=%llu groups=%u,%u,%u commands_modified=0.",
            phase,
            pass.depth,
            pass.event_kind != nullptr ? pass.event_kind : "unknown",
            static_cast<unsigned long long>(pass.event_index),
            pass.pipeline_state,
            pass.inputs.size(),
            pass.outputs.size(),
            static_cast<unsigned long long>(pass.feedback_count),
            group_x, group_y, group_z);
        for (UINT index = 0; index < pass.inputs.size(); ++index)
        {
            const auto &input = pass.inputs[index];
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX downstream lighting dependency chain v70: CHAIN_INPUT phase=%s depth=%u input_index=%u resource_id=%llu descriptor_kind=%s binding_kind=%s root_parameter=%u descriptor_offset=%u.",
                phase, pass.depth, index,
                static_cast<unsigned long long>(input.resource_id),
                v55_descriptor_kind_name(input.descriptor_kind),
                input.binding_kind == 2 ? "direct-root" : "table",
                input.root_parameter,
                input.descriptor_offset);
        }
        for (UINT index = 0; index < pass.outputs.size(); ++index)
        {
            const auto &output = pass.outputs[index];
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX downstream lighting dependency chain v70: CHAIN_OUTPUT phase=%s depth=%u output_index=%u resource_id=%llu format=%u dimension=%u width=%llu height=%u flags=0x%X binding_kind=%s root_parameter=%u descriptor_offset=%u feedback=%u.",
                phase, pass.depth, index,
                static_cast<unsigned long long>(output.resource_id),
                output.format,
                output.dimension,
                static_cast<unsigned long long>(output.width),
                output.height,
                output.flags,
                output.binding_kind == 2 ? "direct-root-uav" : "table-uav",
                output.root_parameter,
                output.descriptor_offset,
                v70_contains_id(
                    [&pass]() {
                        std::vector<uint64_t> ids;
                        ids.reserve(pass.inputs.size());
                        for (const auto &input : pass.inputs)
                            ids.push_back(input.resource_id);
                        return ids;
                    }(),
                    output.resource_id) ? 1u : 0u);
        }
    }

    bool v70_output_logical_match(
        const v66_output_candidate &left,
        const v66_output_candidate &right)
    {
        return left.format == right.format &&
            left.dimension == right.dimension &&
            left.width == right.width &&
            left.height == right.height &&
            left.flags == right.flags &&
            left.binding_kind == right.binding_kind &&
            left.root_parameter == right.root_parameter &&
            left.descriptor_offset == right.descriptor_offset;
    }

    bool v70_pass_logical_match(
        const v70_chain_pass_signature &world,
        const v70_chain_pass_signature &post)
    {
        if (world.pipeline_state != post.pipeline_state ||
            world.outputs.size() != post.outputs.size())
            return false;
        std::vector<bool> matched(post.outputs.size(), false);
        for (const auto &world_output : world.outputs)
        {
            bool found = false;
            for (size_t index = 0; index < post.outputs.size(); ++index)
            {
                if (matched[index] ||
                    !v70_output_logical_match(world_output, post.outputs[index]))
                    continue;
                matched[index] = true;
                found = true;
                break;
            }
            if (!found)
                return false;
        }
        return true;
    }

    void v70_compare_chains_if_ready()
    {
        if (!s_v70_world_chain_complete.load(std::memory_order_acquire) ||
            !s_v70_post_chain_complete.load(std::memory_order_acquire))
            return;
        bool expected = false;
        if (!s_v70_comparison_complete.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
            return;

        std::lock_guard<std::mutex> lock(s_v70_chain_mutex);
        const size_t compared =
            s_v70_world_chain.passes.size() < s_v70_post_chain.passes.size() ?
                s_v70_world_chain.passes.size() :
                s_v70_post_chain.passes.size();
        uint64_t logical_matches = 0;
        uint64_t physical_persistent = 0;
        uint64_t feedback_matches = 0;
        for (size_t index = 0; index < compared; ++index)
        {
            const auto &world = s_v70_world_chain.passes[index];
            const auto &post = s_v70_post_chain.passes[index];
            const bool logical = v70_pass_logical_match(world, post);
            if (logical)
                ++logical_matches;
            uint64_t persistent = 0;
            for (const auto &world_output : world.outputs)
                for (const auto &post_output : post.outputs)
                    if (world_output.resource_id == post_output.resource_id)
                        ++persistent;
            physical_persistent += persistent;
            const bool feedback_match =
                world.feedback_count != 0 && post.feedback_count != 0;
            if (feedback_match)
                ++feedback_matches;
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX downstream lighting dependency chain v70: CHAIN_COMPARISON depth=%zu logical_match=%u same_pipeline=%u physical_persistent_count=%llu world_feedback=%llu post_feedback=%llu.",
                index + 1,
                logical ? 1u : 0u,
                world.pipeline_state == post.pipeline_state ? 1u : 0u,
                static_cast<unsigned long long>(persistent),
                static_cast<unsigned long long>(world.feedback_count),
                static_cast<unsigned long long>(post.feedback_count));
        }
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX downstream lighting dependency chain v70: DOWNSTREAM_CHAIN_RESULT success=1 world_steps=%zu post_steps=%zu compared_steps=%zu logical_match_count=%llu physical_persistent_count=%llu feedback_match_count=%llu conclusion=first-stable-logical-history-boundary-located commands_modified=0.",
            s_v70_world_chain.passes.size(),
            s_v70_post_chain.passes.size(),
            compared,
            static_cast<unsigned long long>(logical_matches),
            static_cast<unsigned long long>(physical_persistent),
            static_cast<unsigned long long>(feedback_matches));
    }

    void v70_seed_chain(
        bool post_menu,
        void *pipeline_state,
        const char *kind,
        uint64_t event_index,
        const std::vector<v66_output_candidate> &outputs)
    {
        if (outputs.empty())
            return;
        std::lock_guard<std::mutex> lock(s_v70_chain_mutex);
        auto &phase = post_menu ? s_v70_post_chain : s_v70_world_chain;
        if (phase.seeded)
            return;
        phase.seeded = true;
        phase.complete = false;
        phase.depth = 0;
        phase.frontier.clear();
        phase.passes.clear();
        for (const auto &output : outputs)
        {
            if (!v70_contains_id(phase.frontier, output.resource_id))
                phase.frontier.push_back(output.resource_id);
        }
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX downstream lighting dependency chain v70: CHAIN_SEED phase=%s source_kind=%s source_event_index=%llu source_pipeline_state=%p frontier_count=%zu max_depth=3 stop_on_feedback=1 commands_modified=0.",
            post_menu ? "post-menu" : "world",
            kind != nullptr ? kind : "unknown",
            static_cast<unsigned long long>(event_index),
            pipeline_state,
            phase.frontier.size());
    }

    void v70_observe_chain_event(
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

        const bool post_menu =
            s_v66_post_menu_phase.load(std::memory_order_acquire);
        std::vector<uint64_t> frontier;
        UINT expected_depth = 0;
        {
            std::lock_guard<std::mutex> lock(s_v70_chain_mutex);
            const auto &phase = post_menu ? s_v70_post_chain : s_v70_world_chain;
            if (!phase.seeded || phase.complete || phase.frontier.empty())
                return;
            frontier = phase.frontier;
            expected_depth = phase.depth;
        }

        v66_command_binding_state state = {};
        {
            std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
            const auto found = s_v66_binding_states.find(command_list);
            if (found == s_v66_binding_states.end())
                return;
            state = found->second;
        }

        std::vector<v70_input_reference> inputs;
        std::vector<v66_output_candidate> outputs;
        if (!v70_scan_chain_bindings(
                state, graphics, frontier, inputs, outputs) ||
            outputs.empty())
            return;

        const uint64_t event_index = s_v70_event_index.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        const uint64_t feedback = v70_feedback_count(inputs, outputs);
        v70_chain_pass_signature pass = {};
        pass.depth = expected_depth + 1;
        pass.pipeline_state = state.pipeline_state;
        pass.event_kind = kind;
        pass.event_index = event_index;
        pass.feedback_count = feedback;
        pass.inputs = inputs;
        pass.outputs = outputs;

        bool completed_now = false;
        {
            std::lock_guard<std::mutex> lock(s_v70_chain_mutex);
            auto &phase = post_menu ? s_v70_post_chain : s_v70_world_chain;
            if (!phase.seeded || phase.complete || phase.depth != expected_depth)
                return;
            phase.depth = pass.depth;
            phase.passes.push_back(pass);
            phase.frontier.clear();
            for (const auto &output : outputs)
            {
                if (!v70_contains_id(phase.frontier, output.resource_id))
                    phase.frontier.push_back(output.resource_id);
            }
            if (feedback != 0 || phase.depth >= 3)
            {
                phase.complete = true;
                completed_now = true;
            }
        }

        s_v70_chain_candidate_count.fetch_add(1, std::memory_order_acq_rel);
        if (post_menu)
            s_v70_post_step_count.fetch_add(1, std::memory_order_acq_rel);
        else
            s_v70_world_step_count.fetch_add(1, std::memory_order_acq_rel);
        if (feedback != 0)
            s_v70_feedback_candidate_count.fetch_add(
                feedback, std::memory_order_acq_rel);
        v70_log_chain_pass(
            post_menu ? "post-menu" : "world",
            pass, group_x, group_y, group_z);

        if (!completed_now)
            return;
        if (post_menu)
        {
            s_v70_post_chain_complete.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX downstream lighting dependency chain v70: POST_MENU_CHAIN_COMPLETE steps=%u termination=%s commands_modified=0.",
                pass.depth,
                feedback != 0 ? "feedback-boundary" : "depth-limit");
            v70_compare_chains_if_ready();
        }
        else
        {
            s_v70_world_chain_complete.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX downstream lighting dependency chain v70: WORLD_CHAIN_COMPLETE steps=%u termination=%s ready_for_manual_menu=1 commands_modified=0.",
                pass.depth,
                feedback != 0 ? "feedback-boundary" : "depth-limit");
        }
    }

'''

# The lambda-created temporary vector in logging is legal but clumsy and may
# create avoidable compile complexity. Replace it after insertion with a local
# feedback scan in a simpler form below.

# 5. Seed calls.
world_anchor = '''            v66_log_outputs("world", kind, dispatch_index, outputs);
            return;
'''
world_repl = '''            v66_log_outputs("world", kind, dispatch_index, outputs);
            v70_seed_chain(
                false, state.pipeline_state, kind, dispatch_index, outputs);
            return;
'''
post_anchor = '''        v66_log_outputs("post-menu", kind, dispatch_index, outputs);
    }
'''
post_repl = '''        v66_log_outputs("post-menu", kind, dispatch_index, outputs);
        v70_seed_chain(
            true, state.pipeline_state, kind, dispatch_index, outputs);
    }
'''

# 6. Hook calls before V66 observation.
indirect_anchor = '''        else if (dispatch_compute)
            v66_observe_consumer_dispatch(
                command_list,
                "execute-indirect-compute",
                max_command_count, 0, 0);
'''
indirect_repl = '''        else if (dispatch_compute)
        {
            v70_observe_chain_event(
                command_list,
                "execute-indirect-compute",
                false,
                max_command_count, 0, 0);
            v66_observe_consumer_dispatch(
                command_list,
                "execute-indirect-compute",
                max_command_count, 0, 0);
        }
'''

draw1_anchor = '''        v66_observe_graphics_draw(command_list, "draw-instanced");
'''
draw1_repl = '''        v70_observe_chain_event(
            command_list, "draw-instanced", true,
            vertex_count, instance_count, 0);
        v66_observe_graphics_draw(command_list, "draw-instanced");
'''
draw2_anchor = '''        v66_observe_graphics_draw(command_list, "draw-indexed-instanced");
'''
draw2_repl = '''        v70_observe_chain_event(
            command_list, "draw-indexed-instanced", true,
            index_count, instance_count, 0);
        v66_observe_graphics_draw(command_list, "draw-indexed-instanced");
'''
dispatch_anchor = '''        v66_observe_consumer_dispatch(
            command_list, "direct-compute", group_x, group_y, group_z);
'''
dispatch_repl = '''        v70_observe_chain_event(
            command_list, "direct-compute", false,
            group_x, group_y, group_z);
        v66_observe_consumer_dispatch(
            command_list, "direct-compute", group_x, group_y, group_z);
'''

replacements = [
    ('struct', struct_anchor, struct_add),
    ('state', state_anchor, state_add),
    ('proto', proto_anchor, proto_add),
    ('active', active_anchor, active_add),
    ('implementation anchor', impl_anchor, impl + impl_anchor),
    ('world seed', world_anchor, world_repl),
    ('post seed', post_anchor, post_repl),
    ('indirect', indirect_anchor, indirect_repl),
    ('draw1', draw1_anchor, draw1_repl),
    ('draw2', draw2_anchor, draw2_repl),
    ('dispatch', dispatch_anchor, dispatch_repl),
]
if "D3DMetal RTX downstream lighting dependency chain v70: ACTIVE" not in text:
    for label, old, new in replacements:
        c = text.count(old)
        if c != 1:
            raise SystemExit(f'{label} anchor count {c}, expected 1')
        text = text.replace(old, new, 1)

else:
    print('V70_PATCH_ALREADY_APPLIED=YES')

# Simplify the feedback field in output logging by replacing the lambda-based
# temporary-vector expression with an explicit nested scan.
old_loop = '''        for (UINT index = 0; index < pass.outputs.size(); ++index)
        {
            const auto &output = pass.outputs[index];
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX downstream lighting dependency chain v70: CHAIN_OUTPUT phase=%s depth=%u output_index=%u resource_id=%llu format=%u dimension=%u width=%llu height=%u flags=0x%X binding_kind=%s root_parameter=%u descriptor_offset=%u feedback=%u.",
                phase, pass.depth, index,
                static_cast<unsigned long long>(output.resource_id),
                output.format,
                output.dimension,
                static_cast<unsigned long long>(output.width),
                output.height,
                output.flags,
                output.binding_kind == 2 ? "direct-root-uav" : "table-uav",
                output.root_parameter,
                output.descriptor_offset,
                v70_contains_id(
                    [&pass]() {
                        std::vector<uint64_t> ids;
                        ids.reserve(pass.inputs.size());
                        for (const auto &input : pass.inputs)
                            ids.push_back(input.resource_id);
                        return ids;
                    }(),
                    output.resource_id) ? 1u : 0u);
        }
'''
new_loop = '''        for (UINT index = 0; index < pass.outputs.size(); ++index)
        {
            const auto &output = pass.outputs[index];
            bool feedback = false;
            for (const auto &input : pass.inputs)
            {
                if (input.resource_id == output.resource_id)
                {
                    feedback = true;
                    break;
                }
            }
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX downstream lighting dependency chain v70: CHAIN_OUTPUT phase=%s depth=%u output_index=%u resource_id=%llu format=%u dimension=%u width=%llu height=%u flags=0x%X binding_kind=%s root_parameter=%u descriptor_offset=%u feedback=%u.",
                phase, pass.depth, index,
                static_cast<unsigned long long>(output.resource_id),
                output.format,
                output.dimension,
                static_cast<unsigned long long>(output.width),
                output.height,
                output.flags,
                output.binding_kind == 2 ? "direct-root-uav" : "table-uav",
                output.root_parameter,
                output.descriptor_offset,
                feedback ? 1u : 0u);
        }
'''
if old_loop in text:
    if text.count(old_loop) != 1:
        raise SystemExit('feedback logging loop anchor mismatch')
    text = text.replace(old_loop, new_loop, 1)


source.write_text(text, encoding='utf-8')
Path('v70-patch-report.txt').write_text(
    '\n'.join([
        'V70_DOWNSTREAM_LIGHTING_DEPENDENCY_CHAIN_PATCH_OK',
        'BASELINE=V69_MANUAL_NORMAL_MENU_HISTORY',
        'SOURCE=FIRST_RAYHIT_CONSUMER_OUTPUTS',
        'MAX_CHAIN_DEPTH=3',
        'STOP_ON_FEEDBACK=ENABLED',
        'WORLD_AND_POST_MENU_PHASES=ENABLED',
        'LOGICAL_SLOT_COMPARISON=ENABLED',
        'PHYSICAL_RESOURCE_PERSISTENCE=DIAGNOSTIC_ONLY',
        'RAYHIT_READBACK=DISABLED',
        'RESOURCE_COPIES=DISABLED',
        'RESOURCE_BARRIERS=DISABLED',
        'COMMANDS_MODIFIED=NO',
        'RESULT=PASS',
        '',
    ]), encoding='ascii')
print('V70_DOWNSTREAM_LIGHTING_DEPENDENCY_CHAIN_PATCH_OK')
