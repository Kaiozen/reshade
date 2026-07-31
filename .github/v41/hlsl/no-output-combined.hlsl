struct RayIntersection_RT
{
    float hitT;
    uint value1;
    uint value2;
    uint value3;
    uint value4;
    uint value5;
};

[shader("raygeneration")]
void ExecuteTrace()
{
}

[shader("miss")]
void Miss(inout RayIntersection_RT rayIntersection)
{
}
