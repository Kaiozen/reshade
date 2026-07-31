struct MinimalPayload
{
    float value;
};

RaytracingAccelerationStructure g_Scene : register(t0);

[shader("raygeneration")]
void ExecuteTrace()
{
    MinimalPayload payload;
    payload.value = 0.0;

    RayDesc ray;
    ray.Origin = float3(0.0, 0.0, 0.0);
    ray.Direction = float3(0.0, 0.0, 1.0);
    ray.TMin = 0.001;
    ray.TMax = 1.0;

    TraceRay(
        g_Scene,
        RAY_FLAG_NONE,
        0xFF,
        0,
        1,
        0,
        ray,
        payload);
}
