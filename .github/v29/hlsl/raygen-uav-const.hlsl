RWByteAddressBuffer g_Output : register(u1);

[shader("raygeneration")]
void ExecuteTrace()
{
    g_Output.Store(0, 0x12345678u);
}
