RWByteAddressBuffer g_Output : register(u1);

[shader("raygeneration")]
void ExecuteTrace()
{
    const uint index = DispatchRaysIndex().x;
    g_Output.Store(0, index);
}
