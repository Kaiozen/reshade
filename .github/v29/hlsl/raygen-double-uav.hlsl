RWByteAddressBuffer g_Output : register(u1);

[shader("raygeneration")]
void ExecuteTrace()
{
    const double value = (double)DispatchRaysIndex().x * 1.0000000001;
    g_Output.Store(0, (uint)value);
}
