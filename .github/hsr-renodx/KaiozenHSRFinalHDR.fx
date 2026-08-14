// Kaiozen HSR Final-Frame HDR10
// The input is the complete HSR frame AFTER scene + UI composition.
// Conversion follows RenoDX's BT.2446A inverse-tone-map implementation,
// then converts BT.709 -> BT.2020 and encodes absolute ST.2084 PQ.

texture2D BackBufferTex : COLOR;

sampler2D BackBufferSampler
{
    Texture = BackBufferTex;
    AddressU = CLAMP;
    AddressV = CLAMP;
    MinFilter = POINT;
    MagFilter = POINT;
    MipFilter = POINT;
    SRGBTexture = false;
};

static const float SDR_WHITE_NITS = 203.0;
static const float HDR_PEAK_NITS = 1000.0;

float3 BT709ToBT2020(float3 c)
{
    float3 o;
    o.r = 0.62740390 * c.r + 0.32928304 * c.g + 0.04331307 * c.b;
    o.g = 0.06909729 * c.r + 0.91954040 * c.g + 0.01136232 * c.b;
    o.b = 0.01639144 * c.r + 0.08801331 * c.g + 0.89559525 * c.b;
    return o;
}

float3 PQEncodeNits(float3 nits)
{
    const float m1 = 2610.0 / 16384.0;
    const float m2 = 128.0 * (2523.0 / 4096.0);
    const float c1 = 3424.0 / 4096.0;
    const float c2 = 32.0 * (2413.0 / 4096.0);
    const float c3 = 32.0 * (2392.0 / 4096.0);

    float3 x = max(nits, 0.0) / 10000.0;
    float3 xm1 = pow(x, m1);
    return pow((c1 + c2 * xm1) / (1.0 + c3 * xm1), m2);
}

float3 BT2446AInverseBT2020(float3 linear2020)
{
    // RenoDX/ITU-R BT.2446A SDR -> HDR inverse tone mapping.
    const float invGamma = 2.4;
    const float gamma = 1.0 / invGamma;

    const float3 k2020 = float3(
        0.262698338956556,
        0.678008765772817,
        0.0592928952706273);

    const float3 chromaDenom =
        2.0 - 2.0 * k2020;

    float3 color = pow(max(linear2020, 0.0), gamma);

    float yTmo = dot(color, k2020);
    float3 chroma = (color - yTmo) / chromaDenom;

    float ySdr = yTmo + max(0.1 * chroma.r, 0.0);

    float pSdr =
        1.0 + 32.0 * pow(SDR_WHITE_NITS / 10000.0, gamma);

    float yC =
        log((ySdr * (pSdr - 1.0)) + 1.0)
        / log(pSdr);

    float yP0 = yC / 1.0770;

    float discriminant =
        max(4.83307641 - 4.604 * yC, 0.0);

    float yP1 =
        (-2.7811 + sqrt(discriminant)) / -2.302;

    float yP2 =
        (yC - 0.5000) / 0.5000;

    float yP;

    if (yP0 <= 0.7399)
        yP = yP0;
    else if (yP1 > 0.7399 && yP1 < 0.9909)
        yP = yP1;
    else if (yP2 >= 0.9909)
        yP = yP2;
    else
        yP = yP1;

    float pHdr =
        1.0 + 32.0 * pow(HDR_PEAK_NITS / 10000.0, gamma);

    float yHdr =
        (pow(pHdr, yP) - 1.0)
        / (pHdr - 1.0);

    float colorScale =
        yHdr > 0.0
            ? ySdr / (1.1 * yHdr)
            : 1.0;

    color =
        (chromaDenom * chroma) / colorScale
        + yHdr;

    color = saturate(color);
    color = pow(color, invGamma);

    // Absolute BT.2020 luminance in nits.
    return color * HDR_PEAK_NITS;
}

void PostProcessVS(
    uint id : SV_VertexID,
    out float4 position : SV_Position,
    out float2 texcoord : TEXCOORD0)
{
    texcoord = float2(
        (id == 2) ? 2.0 : 0.0,
        (id == 1) ? 2.0 : 0.0);

    position = float4(
        texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0),
        0.0,
        1.0);
}

float4 FinalHDRPS(
    float4 position : SV_Position,
    float2 texcoord : TEXCOORD0) : SV_Target
{
    // HSR RenoDX's shader-only path finishes in a gamma ~2.2 domain.
    // Undo that first so the inverse-tone-map works in linear light.
    float3 encoded709 = saturate(tex2D(BackBufferSampler, texcoord).rgb);
    float3 linear709 = pow(encoded709, 2.2);

    // Convert the FINISHED frame to BT.2020 before BT.2446A.
    float3 linear2020 = BT709ToBT2020(linear709);

    // ITU-R BT.2446A inverse tone map provides both highlight expansion
    // and its specified colour scaling instead of arbitrary saturation hacks.
    float3 hdr2020Nits = BT2446AInverseBT2020(linear2020);
    hdr2020Nits = clamp(hdr2020Nits, 0.0, HDR_PEAK_NITS);

    float3 pq = PQEncodeNits(hdr2020Nits);
    return float4(saturate(pq), 1.0);
}

technique KaiozenHSRFinalHDR < enabled = true; >
{
    pass
    {
        PrimitiveTopology = TRIANGLELIST;
        VertexCount = 3;
        VertexShader = PostProcessVS;
        PixelShader = FinalHDRPS;
        SRGBWriteEnable = false;
        BlendEnable = false;
    }
}
