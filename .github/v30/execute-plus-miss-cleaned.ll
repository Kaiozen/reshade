;
; Note: shader requires additional functionality:
;       Double-precision floating point
;       UAVs at every shader stage
;       Double-precision extensions for 11.1
;
; shader hash: 30abe7deac812a95c9b4bbaa6b34c3ae
;
; Buffer Definitions:
;
; cbuffer $Globals
; {
;
;   struct hostlayout.$Globals
;   {
;
;       uint _DebugFeature;                           ; Offset:    0
;       column_major float4x4 _InvCameraViewProj;     ; Offset:   16
;       float4 _ScaledScreenParams;                   ; Offset:   80
;       float4 _MainLightPosition;                    ; Offset:   96
;       float4 _MainLightColor;                       ; Offset:  112
;       float4 _DrawObjectPassData;                   ; Offset:  128
;       float4 _ParticleLightParams;                  ; Offset:  144
;       float4 _SceneParticleFogColorMultiply;        ; Offset:  160
;       float4 _KodamaGIParams;                       ; Offset:  176
;       float _SampleLightmapAreaDirect;              ; Offset:  192
;       column_major float4x4 _GlobalTimeParamsA;     ; Offset:  208
;       column_major float4x4 _GlobalTimeParamsB;     ; Offset:  272
;       float4 _GlobalSceneEffectParams;              ; Offset:  336
;       float4 _AvatarPosition0;                      ; Offset:  352
;       column_major float4x4 _FXCC_LutToneParams;    ; Offset:  368
;       float _ShadowPancaking;                       ; Offset:  432
;       float4 _GlobalLightParams;                    ; Offset:  448
;       float4 _GlobalLightParams2;                   ; Offset:  464
;       float3 _WorldSpaceCameraPos;                  ; Offset:  480
;       column_major float4x4 _SceneWeatherParamsPart1;; Offset:  496
;       column_major float4x4 _SceneWeatherParamsPart2;; Offset:  560
;       column_major float4x4 _SceneWeatherParamsPart3;; Offset:  624
;       column_major float4x4 _SceneWeatherParamsPart4;; Offset:  688
;       column_major float4x4 _SceneWeatherParamsPart5;; Offset:  752
;       column_major float4x4 _SceneWeatherParamsPart6;; Offset:  816
;       column_major float4x4 _SceneWeatherParamsPart7;; Offset:  880
;       float4 _ProjectionParams;                     ; Offset:  944
;       float4 _ScreenParams;                         ; Offset:  960
;       float _GlobalMipBias;                         ; Offset:  976
;       float4 _ZBufferParams;                        ; Offset:  992
;       float4 unity_OrthoParams;                     ; Offset: 1008
;       float4 unity_CameraWorldClipPlanes[6];        ; Offset: 1024
;       column_major float4x4 unity_CameraProjection; ; Offset: 1120
;       column_major float4x4 unity_CameraInvProjection;; Offset: 1184
;       column_major float4x4 unity_WorldToCamera;    ; Offset: 1248
;       column_major float4x4 unity_CameraToWorld;    ; Offset: 1312
;       column_major float4x4 glstate_matrix_transpose_modelview0;; Offset: 1376
;       column_major float4x4 glstate_matrix_projection;; Offset: 1440
;       column_major float4x4 unity_MatrixV;          ; Offset: 1504
;       column_major float4x4 unity_MatrixInvV;       ; Offset: 1568
;       column_major float4x4 unity_MatrixVP;         ; Offset: 1632
;       column_major float4x4 unity_MatrixInvVP;      ; Offset: 1696
;       column_major float4x4 _PrevViewProjMatrix;    ; Offset: 1760
;       column_major float4x4 _PrevInvViewProjMatrix; ; Offset: 1824
;       column_major float4x4 _NonJitteredViewProjMatrix;; Offset: 1888
;       column_major float4x4 _NonJitteredProjMatrix; ; Offset: 1952
;       column_major float4x4 _PrevViewMatrix;        ; Offset: 2016
;       column_major float4x4 _PrevProjMatrix;        ; Offset: 2080
;       column_major float4x4 _InvViewProjMatrix;     ; Offset: 2144
;       float4 _ScreenSize;                           ; Offset: 2208
;       float4 _TaaFrameInfo;                         ; Offset: 2224
;       float4 _TaaJitterStrength;                    ; Offset: 2240
;       column_major float4x4 _FxFogParamsPartA;      ; Offset: 2256
;       column_major float4x4 _FxFogParamsPartB;      ; Offset: 2320
;       column_major float4x4 _SceneFogParamsPart1;   ; Offset: 2384
;       column_major float4x4 _SceneFogParamsPart2;   ; Offset: 2448
;       column_major float4x4 _SceneFogParamsPart3;   ; Offset: 2512
;       column_major float4x4 _SceneFogParamsPart4;   ; Offset: 2576
;       float4 _SkyHorizontalParam;                   ; Offset: 2640
;       float4 _AlphaBlendAlphaParams;                ; Offset: 2656
;       column_major float4x4 _FullscreenProjMat;     ; Offset: 2672
;       uint _PunctualLightCount;                     ; Offset: 2736
;       uint _EnvLightCount;                          ; Offset: 2740
;       int g_iLog2NumClusters;                       ; Offset: 2744
;       uint _NumTileClusteredX;                      ; Offset: 2748
;       uint _NumTileClusteredY;                      ; Offset: 2752
;       float g_fClustBase;                           ; Offset: 2756
;       column_major float4x4 _P_Inv;                 ; Offset: 2768
;       column_major float4x4 _V_Inv;                 ; Offset: 2832
;       float4 _Pixel_WH;                             ; Offset: 2896
;       int _Frame_Index;                             ; Offset: 2912
;       float4 _IrradianceVolumeCenter;               ; Offset: 2928
;       float4 _KodamaVolumeTextureSize0;             ; Offset: 2944
;       float4 _KodamaVolumeTextureSize1;             ; Offset: 2960
;       float4 _KodamaVolumeTextureSizeInv0;          ; Offset: 2976
;       float4 _KodamaVolumeTextureSizeInv1;          ; Offset: 2992
;       float4 _KodamaVolumeBoundsSizeInv0;           ; Offset: 3008
;       float4 _KodamaVolumeBoundsSizeInv1;           ; Offset: 3024
;       float4 _KodamaVolumeBoundsMin0;               ; Offset: 3040
;       float4 _KodamaVolumeBoundsMin1;               ; Offset: 3056
;       float4 _KodamaSkyIrradianceX;                 ; Offset: 3072
;       float4 _KodamaSkyIrradianceNX;                ; Offset: 3088
;       float4 _KodamaSkyIrradianceY;                 ; Offset: 3104
;       float4 _KodamaSkyIrradianceNY;                ; Offset: 3120
;       float4 _KodamaSkyIrradianceZ;                 ; Offset: 3136
;       float4 _KodamaSkyIrradianceNZ;                ; Offset: 3152
;       float _SmoothnessThreshold;                   ; Offset: 3168
;       float _RTXGIBoost;                            ; Offset: 3172
;       float _RTXGISkyMultiplier;                    ; Offset: 3176
;       float _RTXGIResponseSpeed;                    ; Offset: 3180
;       float _RTXGIEnableLut;                        ; Offset: 3184
;       float _RTXGISkyMultiplierSpec;                ; Offset: 3188
;       float _RTXGIMicroAO;                          ; Offset: 3192
;       float _RTXGISpecBoost;                        ; Offset: 3196
;       float _RTXGIMultiBounceScale;                 ; Offset: 3200
;       float _RTXGIMultiBounceFarDistScale;          ; Offset: 3204
;       float _RTXGIEnableMultiBounceAlbedoLut;       ; Offset: 3208
;       float _RTXGIMultiBounceScaleMaxDist;          ; Offset: 3212
;       float _RTXGIEnableRoughnessLut;               ; Offset: 3216
;       float _RTXGIEnableMetallicLut;                ; Offset: 3220
;       uint _FrameIndex;                             ; Offset: 3224
;       int _RayBudget;                               ; Offset: 3228
;       float4 _Resolution;                           ; Offset: 3232
;       float _RTXGILightmapBoost;                    ; Offset: 3248
;       int _UseRTXGlobalRoughnessLUT;                ; Offset: 3252
;       float _RTXGIShadingTraceShadow;               ; Offset: 3256
;       float _RTXGIDisableSSReshade;                 ; Offset: 3260
;       float _RTXGIShadingTraceShadowDiffuse;        ; Offset: 3264
;       float _RTXGIShadingTraceShadowSpecular;       ; Offset: 3268
;       float _RTXGIEnableForwardGBuffer;             ; Offset: 3272
;       int _RTXGIQualityPreset;                      ; Offset: 3276
;       float _RTXGIRayTraceBias;                     ; Offset: 3280
;       int RTXAOQuality;                             ; Offset: 3284
;       float _RTXAODirectLightPreserve;              ; Offset: 3288
;       float _RTXGIAddLocallightMinDist;             ; Offset: 3292
;       float _RTXGIAddLocallightMaxDist;             ; Offset: 3296
;       float _RTXGIAddLocallightScale;               ; Offset: 3300
;       float _RTXGIAddLocallightExtraMinDist;        ; Offset: 3304
;       float _RTXGIAddLocallightExtraMaxDist;        ; Offset: 3308
;       float _RTXGIAddLocallightExtraScale;          ; Offset: 3312
;       float _RTXGIHueExcludeMin;                    ; Offset: 3316
;       float _RTXGIHueExcludeMax;                    ; Offset: 3320
;       float _RTXGIHueExcludeFade;                   ; Offset: 3324
;       float _RTXGISatThreshold;                     ; Offset: 3328
;       float _RTXGISatThresholdMax;                  ; Offset: 3332
;       float _RTXGIValThreshold;                     ; Offset: 3336
;       float _RTXGIValThresholdMax;                  ; Offset: 3340
;       float _RTXGIHueBoostSat;                      ; Offset: 3344
;       float _RTXGIHueBoostVal;                      ; Offset: 3348
;       float _RTXGIHitHueExcludeMin;                 ; Offset: 3352
;       float _RTXGIHitHueExcludeMax;                 ; Offset: 3356
;       float _RTXGIHitHueExcludeFade;                ; Offset: 3360
;       float _RTXGIHitSatThreshold;                  ; Offset: 3364
;       float _RTXGIHitSatThresholdMax;               ; Offset: 3368
;       float _RTXGIHitValThreshold;                  ; Offset: 3372
;       float _RTXGIHitValThresholdMax;               ; Offset: 3376
;       float _RTXGIHitSatBoost;                      ; Offset: 3380
;       float _RTXGIHitValBoost;                      ; Offset: 3384
;       float _RTXGISpecularHitSatThreshold;          ; Offset: 3388
;       float _RTXGISpecularHitSatThresholdMax;       ; Offset: 3392
;       float _RTXGISpecularHitValThreshold;          ; Offset: 3396
;       float _RTXGISpecularHitValThresholdMax;       ; Offset: 3400
;       float _RTXGISpecularHitSatBoost;              ; Offset: 3404
;       float _RTXGISpecularHitValBoost;              ; Offset: 3408
;       float _RTXGISpecularSatThreshold;             ; Offset: 3412
;       float _RTXGISpecularSatThresholdMax;          ; Offset: 3416
;       float _RTXGISpecularValThreshold;             ; Offset: 3420
;       float _RTXGISpecularValThresholdMax;          ; Offset: 3424
;       float _RTXGISpecularHueBoostSat;              ; Offset: 3428
;       float _RTXGISpecularHueBoostVal;              ; Offset: 3432
;       float _RTXGIHitScatterScale;                  ; Offset: 3436
;       float _RTXGISpecularScatterScale;             ; Offset: 3440
;       float _RTXGIEmissionScatterScale;             ; Offset: 3444
;       float _RTXGIExtraEmissionScaleHighLum;        ; Offset: 3448
;       float _RTXGIExtraEmissionLumMin;              ; Offset: 3452
;       float _RTXGIExtraEmissionLumMax;              ; Offset: 3456
;       float _RTXGIExtraEmissionScaleSpecular;       ; Offset: 3460
;       float _RTXGIDirBiasStrength;                  ; Offset: 3464
;       float _RTXGIBandBiasPower;                    ; Offset: 3468
;       float _RTXGIUpSuppressStrength;               ; Offset: 3472
;       float _RTXGIRestirSatWeight;                  ; Offset: 3476
;       float _RTXGIHistorySatBoost;                  ; Offset: 3480
;       float _RTXGICacheSatInjectScale;              ; Offset: 3484
;       float _RTXGIThresholdRelax;                   ; Offset: 3488
;       float _RTXGIColorBleedChromaBoost;            ; Offset: 3492
;       float _RTXGIHueSimThreshold;                  ; Offset: 3496
;       float _RTXGISatSimThreshold;                  ; Offset: 3500
;       float _RTXGIValSimThreshold;                  ; Offset: 3504
;       float _RTXGIReceiverSatRangeMin;              ; Offset: 3508
;       float _RTXGIReceiverSatRangeMax;              ; Offset: 3512
;       float _RTXGIReceiverSatMinMultiplier;         ; Offset: 3516
;       float _RTXGIReceiverDownDotThreshold;         ; Offset: 3520
;       float _RTXGIReceiverDownDotScale;             ; Offset: 3524
;       float _RTXGIReceiverCameraZDiffThreshold;     ; Offset: 3528
;       float _RTXGIInverseBentBiasEnabled;           ; Offset: 3532
;       float _RTXGIInverseBentBiasStrength;          ; Offset: 3536
;       float _RTXGIScreenSteerEnabled;               ; Offset: 3540
;       float _RTXGIScreenSteerStrength;              ; Offset: 3544
;       float _RTXGIDistWeightEnabled;                ; Offset: 3548
;       float _RTXGIDistWeightExp;                    ; Offset: 3552
;       float4 _SceneUserLut_Params;                  ; Offset: 3568
;       float _SceneLutContribution;                  ; Offset: 3584
;       float4 _ExposureParams;                       ; Offset: 3600
;       float4 _Levels;                               ; Offset: 3616
;       float2 _TLutResolution;                       ; Offset: 3632
;       float _PlanetRadius;                          ; Offset: 3640
;       float _AtmosphereThickness;                   ; Offset: 3644
;       float3 _GroundAlbedo;                         ; Offset: 3648
;       float3 _RayleighScatter;                      ; Offset: 3664
;       float _MeiScatter;                            ; Offset: 3676
;       float _OZone;                                 ; Offset: 3680
;       float _MultiScatterStrength;                  ; Offset: 3684
;       float3 _SunDir;                               ; Offset: 3696
;       float3 _SunLuminance;                         ; Offset: 3712
;       int _WorldLightGridTopKEnable;                ; Offset: 3724
;       float4 _RTXGIMainLightColor;                  ; Offset: 3728
;       float4 _ShadowBias;                           ; Offset: 3744
;       column_major float4x4 _PixelCoordToViewDirWS; ; Offset: 3760
;       column_major float4x4 _DaySkyParamsPartA;     ; Offset: 3824
;       column_major float4x4 _NightSkyParamsPartA;   ; Offset: 3888
;       column_major float4x4 _MoonAndGalaxyDir;      ; Offset: 3952
;       float4 _MoonGlow2Params;                      ; Offset: 4016
;       float _CloudSwitch;                           ; Offset: 4032
;       column_major float4x4 _CloudParamsPartA;      ; Offset: 4048
;       column_major float4x4 _CloudParamsPartB;      ; Offset: 4112
;       float4 _CloudShadowMoveSpeed;                 ; Offset: 4176
;       float4 _CloudLightParams1;                    ; Offset: 4192
;       float4 _CloudLightParams2;                    ; Offset: 4208
;       float4 _GlobalWindDirection;                  ; Offset: 4224
;       float _OverrideSkyWeight;                     ; Offset: 4240
;       column_major float4x4 _OverrideSkyParamsPartA;; Offset: 4256
;       int _Procedural;                              ; Offset: 4320
;       float3 _Tint;                                 ; Offset: 4324
;       float _Exposure;                              ; Offset: 4336
;       float _Rotation;                              ; Offset: 4340
;       float4 _MainTex_HDR;                          ; Offset: 4352
;       float4 _SkySHAr;                              ; Offset: 4368
;       float4 _SkySHAg;                              ; Offset: 4384
;       float4 _SkySHAb;                              ; Offset: 4400
;       float4 _SkySHBr;                              ; Offset: 4416
;       float4 _SkySHBg;                              ; Offset: 4432
;       float4 _SkySHBb;                              ; Offset: 4448
;       float4 _SkySHC;                               ; Offset: 4464
;       column_major float4x4 _LastVP;                ; Offset: 4480
;       column_major float4x4 _LastVPInv;             ; Offset: 4544
;       float4 _LastCameraPos;                        ; Offset: 4608
;       int _RayPixelIdBufferCount;                   ; Offset: 4624
;       int _PackedSpecRayInfoBufferCount;            ; Offset: 4628
;       int _RayHitBufferCount;                       ; Offset: 4632
;   
;   } $Globals;                                       ; Offset:    0 Size:  4636
;
; }
;
; Resource bind info for _RayPixelIdBuffer
; {
;
;   uint $Element;                                    ; Offset:    0 Size:     4
;
; }
;
; Resource bind info for _PackedSpecRayInfoBuffer
; {
;
;   uint2 $Element;                                   ; Offset:    0 Size:     8
;
; }
;
; Resource bind info for _RayAllocatorBuffer
; {
;
;   uint $Element;                                    ; Offset:    0 Size:     4
;
; }
;
; Resource bind info for _RWRayHitBuffer
; {
;
;   struct struct.RayIntersection_Data
;   {
;
;       uint4 data012;                                ; Offset:    0
;       uint data3;                                   ; Offset:   16
;       uint data4;                                   ; Offset:   20
;   
;   } $Element;                                       ; Offset:    0 Size:    24
;
; }
;
;
; Resource Bindings:
;
; Name                                 Type  Format         Dim      ID      HLSL Bind  Count
; ------------------------------ ---------- ------- ----------- ------- -------------- ------
; $Globals                          cbuffer      NA          NA     CB0            cb0     1
; _RaytracingAccelerationStructure   texture     i32         ras      T0             t0     1
; _PackedRayInfo0                   texture     u32          2d      T1             t1     1
; _SceneNormal                      texture     f32          2d      T2             t2     1
; _RayPixelIdBuffer                 texture  struct         r/o      T3             t3     1
; _PackedSpecRayInfoBuffer          texture  struct         r/o      T4             t4     1
; _RayAllocatorBuffer               texture  struct         r/o      T5             t5     1
; _SceneForwardDepth                texture     f32          2d      T6             t6     1
; _SceneForwardNormal               texture     f32          2d      T7             t7     1
; _RWRaySortBuffer                      UAV    byte         r/w      U0             u0     1
; _RWRayHitBuffer                       UAV  struct         r/w      U1             u1     1
;
target datalayout = "e-m:e-p:32:32-i1:32-i8:32-i16:32-i32:32-i64:64-f16:32-f32:32-f64:64-n8:16:32:64"
target triple = "dxil-ms-dx"

%struct.RaytracingAccelerationStructure = type { i32 }
%"class.Texture2D<vector<unsigned int, 2> >" = type { <2 x i32>, %"class.Texture2D<vector<unsigned int, 2> >::mips_type" }
%"class.Texture2D<vector<unsigned int, 2> >::mips_type" = type { i32 }
%"class.Texture2D<vector<float, 4> >" = type { <4 x float>, %"class.Texture2D<vector<float, 4> >::mips_type" }
%"class.Texture2D<vector<float, 4> >::mips_type" = type { i32 }
%"class.StructuredBuffer<unsigned int>" = type { i32 }
%"class.StructuredBuffer<vector<unsigned int, 2> >" = type { <2 x i32> }
%"class.RWStructuredBuffer<RayIntersection_Data>" = type { %struct.RayIntersection_Data }
%struct.RayIntersection_Data = type { <4 x i32>, i32, i32 }
%"class.Texture2D<float>" = type { float, %"class.Texture2D<float>::mips_type" }
%"class.Texture2D<float>::mips_type" = type { i32 }
%"hostlayout.$Globals" = type { i32, [4 x <4 x float>], <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, float, [4 x <4 x float>], [4 x <4 x float>], <4 x float>, <4 x float>, [4 x <4 x float>], float, <4 x float>, <4 x float>, <3 x float>, [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], <4 x float>, <4 x float>, float, <4 x float>, <4 x float>, [6 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], <4 x float>, <4 x float>, <4 x float>, [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], <4 x float>, <4 x float>, [4 x <4 x float>], i32, i32, i32, i32, i32, float, [4 x <4 x float>], [4 x <4 x float>], <4 x float>, i32, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, float, float, float, float, float, float, float, float, float, float, float, float, float, float, i32, i32, <4 x float>, float, i32, float, float, float, float, float, i32, float, i32, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, <4 x float>, float, <4 x float>, <4 x float>, <2 x float>, float, float, <3 x float>, <3 x float>, float, float, float, <3 x float>, <3 x float>, i32, <4 x float>, <4 x float>, [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], [4 x <4 x float>], <4 x float>, float, [4 x <4 x float>], [4 x <4 x float>], <4 x float>, <4 x float>, <4 x float>, <4 x float>, float, [4 x <4 x float>], i32, <3 x float>, float, float, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, <4 x float>, [4 x <4 x float>], [4 x <4 x float>], <4 x float>, i32, i32, i32 }
%struct.RayIntersection_RT = type { float, i32, i32, i32, i32, i32 }
%dx.types.Handle = type { i8* }
%dx.types.ResRet.i32 = type { i32, i32, i32, i32, i32 }
%dx.types.CBufRet.i32 = type { i32, i32, i32, i32 }
%dx.types.ResRet.f32 = type { float, float, float, float, i32 }
%dx.types.CBufRet.f32 = type { float, float, float, float }

@"\01?_RaytracingAccelerationStructure@@3URaytracingAccelerationStructure@@A" = external constant %struct.RaytracingAccelerationStructure, align 4
@"\01?_PackedRayInfo0@@3V?$Texture2D@V?$vector@I$01@@@@A" = external constant %"class.Texture2D<vector<unsigned int, 2> >", align 4
@"\01?_SceneNormal@@3V?$Texture2D@V?$vector@M$03@@@@A" = external constant %"class.Texture2D<vector<float, 4> >", align 4
@"\01?_RayPixelIdBuffer@@3V?$StructuredBuffer@I@@A" = external constant %"class.StructuredBuffer<unsigned int>", align 4
@"\01?_PackedSpecRayInfoBuffer@@3V?$StructuredBuffer@V?$vector@I$01@@@@A" = external constant %"class.StructuredBuffer<vector<unsigned int, 2> >", align 4
@"\01?_RWRayHitBuffer@@3V?$RWStructuredBuffer@URayIntersection_Data@@@@A" = external constant %"class.RWStructuredBuffer<RayIntersection_Data>", align 4
@"\01?_RayAllocatorBuffer@@3V?$StructuredBuffer@I@@A" = external constant %"class.StructuredBuffer<unsigned int>", align 4
@"\01?_SceneForwardDepth@@3V?$Texture2D@M@@A" = external constant %"class.Texture2D<float>", align 4
@"\01?_SceneForwardNormal@@3V?$Texture2D@V?$vector@M$03@@@@A" = external constant %"class.Texture2D<vector<float, 4> >", align 4
@llvm.global_ctors = appending global [0 x { i32, void ()*, i8* }] zeroinitializer
@"$Globals_legacy" = external global %"hostlayout.$Globals"

; Function Attrs: nounwind
define void @"\01?ExecuteTrace@@YAXXZ"() #0 {
  %1 = load %"class.Texture2D<vector<float, 4> >", %"class.Texture2D<vector<float, 4> >"* @"\01?_SceneForwardNormal@@3V?$Texture2D@V?$vector@M$03@@@@A", align 4, !noalias !39
  %2 = load %"class.Texture2D<float>", %"class.Texture2D<float>"* @"\01?_SceneForwardDepth@@3V?$Texture2D@M@@A", align 4, !noalias !39
  %3 = load %"class.StructuredBuffer<unsigned int>", %"class.StructuredBuffer<unsigned int>"* @"\01?_RayAllocatorBuffer@@3V?$StructuredBuffer@I@@A", align 4
  %4 = load %"class.StructuredBuffer<vector<unsigned int, 2> >", %"class.StructuredBuffer<vector<unsigned int, 2> >"* @"\01?_PackedSpecRayInfoBuffer@@3V?$StructuredBuffer@V?$vector@I$01@@@@A", align 4, !noalias !42
  %5 = load %"class.StructuredBuffer<unsigned int>", %"class.StructuredBuffer<unsigned int>"* @"\01?_RayPixelIdBuffer@@3V?$StructuredBuffer@I@@A", align 4, !noalias !46
  %6 = load %"class.Texture2D<vector<float, 4> >", %"class.Texture2D<vector<float, 4> >"* @"\01?_SceneNormal@@3V?$Texture2D@V?$vector@M$03@@@@A", align 4, !noalias !50
  %7 = load %"class.Texture2D<vector<unsigned int, 2> >", %"class.Texture2D<vector<unsigned int, 2> >"* @"\01?_PackedRayInfo0@@3V?$Texture2D@V?$vector@I$01@@@@A", align 4, !noalias !50
  %8 = load %struct.RaytracingAccelerationStructure, %struct.RaytracingAccelerationStructure* @"\01?_RaytracingAccelerationStructure@@3URaytracingAccelerationStructure@@A", align 4
  %9 = load %"class.RWStructuredBuffer<RayIntersection_Data>", %"class.RWStructuredBuffer<RayIntersection_Data>"* @"\01?_RWRayHitBuffer@@3V?$RWStructuredBuffer@URayIntersection_Data@@@@A", align 4
  %10 = load %"hostlayout.$Globals", %"hostlayout.$Globals"* @"$Globals_legacy"
  %11 = alloca %struct.RayIntersection_RT, align 4
  %12 = call %dx.types.Handle @"dx.op.createHandleForLib.hostlayout.$Globals"(i32 160, %"hostlayout.$Globals" %10)  ; CreateHandleForLib(Resource)
  %13 = call %dx.types.Handle @"dx.op.createHandleForLib.class.StructuredBuffer<unsigned int>"(i32 160, %"class.StructuredBuffer<unsigned int>" %3)  ; CreateHandleForLib(Resource)
  %14 = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %13, i32 1, i32 0, i8 1, i32 4)  ; RawBufferLoad(srv,index,elementOffset,mask,alignment)
  %15 = extractvalue %dx.types.ResRet.i32 %14, 0
  %16 = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %13, i32 2, i32 0, i8 1, i32 4)  ; RawBufferLoad(srv,index,elementOffset,mask,alignment)
  %17 = extractvalue %dx.types.ResRet.i32 %16, 0
  %18 = add i32 %17, %15
  %19 = call i32 @dx.op.dispatchRaysIndex.i32(i32 145, i8 0)  ; DispatchRaysIndex(col)
  %20 = uitofp i32 %19 to float
  %21 = bitcast float %20 to i32
  %22 = and i32 %21, 2139095040
  %23 = icmp ugt i32 %22, 2139095039
  %24 = icmp uge i32 %19, %18
  %25 = or i1 %24, %23
  br i1 %25, label %414, label %26

; <label>:26                                      ; preds = %0
  %27 = icmp ult i32 %19, %15
  %28 = call %dx.types.CBufRet.i32 @dx.op.cbufferLoadLegacy.i32(i32 59, %dx.types.Handle %12, i32 289)  ; CBufferLoadLegacy(handle,regIndex)
  br i1 %27, label %29, label %148, !dx.controlflow.hints !53

; <label>:29                                      ; preds = %26
  %30 = extractvalue %dx.types.CBufRet.i32 %28, 0
  %31 = icmp ult i32 %19, %30
  br i1 %31, label %32, label %316

; <label>:32                                      ; preds = %29
  %33 = call %dx.types.Handle @"dx.op.createHandleForLib.class.StructuredBuffer<unsigned int>"(i32 160, %"class.StructuredBuffer<unsigned int>" %5)  ; CreateHandleForLib(Resource)
  %34 = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %33, i32 %19, i32 0, i8 1, i32 4)  ; RawBufferLoad(srv,index,elementOffset,mask,alignment)
  %35 = extractvalue %dx.types.ResRet.i32 %34, 0
  %36 = and i32 %35, 65535
  %37 = lshr i32 %35, 16
  %38 = call %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<vector<float, 4> >"(i32 160, %"class.Texture2D<vector<float, 4> >" %6)  ; CreateHandleForLib(Resource)
  %39 = call %dx.types.ResRet.f32 @dx.op.textureLoad.f32(i32 66, %dx.types.Handle %38, i32 0, i32 %36, i32 %37, i32 undef, i32 undef, i32 undef, i32 undef)  ; TextureLoad(srv,mipLevelOrSampleCount,coord0,coord1,coord2,offset0,offset1,offset2)
  %40 = extractvalue %dx.types.ResRet.f32 %39, 0
  %41 = extractvalue %dx.types.ResRet.f32 %39, 1
  %42 = extractvalue %dx.types.ResRet.f32 %39, 2
  %43 = fmul fast float %40, 2.000000e+00
  %44 = fmul fast float %41, 2.000000e+00
  %45 = fmul fast float %42, 2.000000e+00
  %46 = fadd fast float %43, -1.000000e+00
  %47 = fadd fast float %44, -1.000000e+00
  %48 = fadd fast float %45, -1.000000e+00
  %49 = call float @dx.op.dot3.f32(i32 55, float %46, float %47, float %48, float %46, float %47, float %48)  ; Dot3(ax,ay,az,bx,by,bz)
  %50 = call float @dx.op.binary.f32(i32 35, float 0x3810000000000000, float %49)  ; FMax(a,b)
  %51 = call float @dx.op.unary.f32(i32 25, float %50)  ; Rsqrt(value)
  %52 = fmul fast float %46, %51
  %53 = fmul fast float %47, %51
  %54 = fmul fast float %48, %51
  %55 = call %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<vector<unsigned int, 2> >"(i32 160, %"class.Texture2D<vector<unsigned int, 2> >" %7)  ; CreateHandleForLib(Resource)
  %56 = call %dx.types.ResRet.i32 @dx.op.textureLoad.i32(i32 66, %dx.types.Handle %55, i32 0, i32 %36, i32 %37, i32 undef, i32 undef, i32 undef, i32 undef)  ; TextureLoad(srv,mipLevelOrSampleCount,coord0,coord1,coord2,offset0,offset1,offset2)
  %57 = extractvalue %dx.types.ResRet.i32 %56, 0
  %58 = extractvalue %dx.types.ResRet.i32 %56, 1
  %59 = and i32 %57, 16777215
  %60 = uitofp i32 %59 to double
  %61 = fmul fast double %60, 0x3E70000010000010
  %62 = fptrunc double %61 to float
  %63 = lshr i32 %58, 12
  %64 = and i32 %63, 4095
  %65 = and i32 %58, 4095
  %66 = uitofp i32 %64 to float
  %67 = uitofp i32 %65 to float
  %68 = fmul fast float %66, 0x3F40010020000000
  %69 = fmul fast float %67, 0x3F40010020000000
  %70 = fadd fast float %68, -1.000000e+00
  %71 = fadd fast float %69, -1.000000e+00
  %72 = call float @dx.op.unary.f32(i32 6, float %70)  ; FAbs(value)
  %73 = call float @dx.op.unary.f32(i32 6, float %71)  ; FAbs(value)
  %74 = call float @dx.op.dot2.f32(i32 54, float 1.000000e+00, float 1.000000e+00, float %72, float %73)  ; Dot2(ax,ay,bx,by)
  %75 = fsub fast float 1.000000e+00, %74
  %76 = fcmp fast olt float %75, 0.000000e+00
  br i1 %76, label %77, label %86

; <label>:77                                      ; preds = %32
  %78 = fsub fast float 1.000000e+00, %73
  %79 = fsub fast float 1.000000e+00, %72
  %80 = fcmp fast oge float %70, 0.000000e+00
  %81 = fcmp fast oge float %71, 0.000000e+00
  %82 = select i1 %80, float 0x3FEFFFEB00000000, float -1.000000e+00
  %83 = select i1 %81, float 0x3FEFFFEB00000000, float -1.000000e+00
  %84 = fmul fast float %78, %82
  %85 = fmul fast float %79, %83
  br label %86

; <label>:86                                      ; preds = %77, %32
  %87 = phi float [ %84, %77 ], [ %70, %32 ]
  %88 = phi float [ %85, %77 ], [ %71, %32 ]
  %89 = call float @dx.op.dot3.f32(i32 55, float %87, float %88, float %75, float %87, float %88, float %75)  ; Dot3(ax,ay,az,bx,by,bz)
  %90 = call float @dx.op.binary.f32(i32 35, float 0x3810000000000000, float %89)  ; FMax(a,b)
  %91 = call float @dx.op.unary.f32(i32 25, float %90)  ; Rsqrt(value)
  %92 = fmul fast float %91, %87
  %93 = fmul fast float %91, %88
  %94 = fmul fast float %91, %75
  %95 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 134)  ; CBufferLoadLegacy(handle,regIndex)
  %96 = extractvalue %dx.types.CBufRet.f32 %95, 0
  %97 = extractvalue %dx.types.CBufRet.f32 %95, 1
  %98 = extractvalue %dx.types.CBufRet.f32 %95, 2
  %99 = extractvalue %dx.types.CBufRet.f32 %95, 3
  %100 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 135)  ; CBufferLoadLegacy(handle,regIndex)
  %101 = extractvalue %dx.types.CBufRet.f32 %100, 0
  %102 = extractvalue %dx.types.CBufRet.f32 %100, 1
  %103 = extractvalue %dx.types.CBufRet.f32 %100, 2
  %104 = extractvalue %dx.types.CBufRet.f32 %100, 3
  %105 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 136)  ; CBufferLoadLegacy(handle,regIndex)
  %106 = extractvalue %dx.types.CBufRet.f32 %105, 0
  %107 = extractvalue %dx.types.CBufRet.f32 %105, 1
  %108 = extractvalue %dx.types.CBufRet.f32 %105, 2
  %109 = extractvalue %dx.types.CBufRet.f32 %105, 3
  %110 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 137)  ; CBufferLoadLegacy(handle,regIndex)
  %111 = extractvalue %dx.types.CBufRet.f32 %110, 0
  %112 = extractvalue %dx.types.CBufRet.f32 %110, 1
  %113 = extractvalue %dx.types.CBufRet.f32 %110, 2
  %114 = extractvalue %dx.types.CBufRet.f32 %110, 3
  %115 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 202)  ; CBufferLoadLegacy(handle,regIndex)
  %116 = extractvalue %dx.types.CBufRet.f32 %115, 2
  %117 = extractvalue %dx.types.CBufRet.f32 %115, 3
  %118 = sitofp i32 %36 to float
  %119 = sitofp i32 %37 to float
  %120 = fadd fast float %118, 5.000000e-01
  %121 = fadd fast float %119, 5.000000e-01
  %122 = fmul fast float %120, 2.000000e+00
  %123 = fmul fast float %122, %116
  %124 = fmul fast float %121, 2.000000e+00
  %125 = fmul fast float %124, %117
  %126 = fadd fast float %123, -1.000000e+00
  %127 = fadd fast float %125, -1.000000e+00
  %128 = fsub fast float -0.000000e+00, %127
  %129 = fmul fast float %126, %96
  %130 = call float @dx.op.tertiary.f32(i32 46, float %101, float %128, float %129)  ; FMad(a,b,c)
  %131 = call float @dx.op.tertiary.f32(i32 46, float %106, float %62, float %130)  ; FMad(a,b,c)
  %132 = fadd fast float %131, %111
  %133 = fmul fast float %126, %97
  %134 = call float @dx.op.tertiary.f32(i32 46, float %102, float %128, float %133)  ; FMad(a,b,c)
  %135 = call float @dx.op.tertiary.f32(i32 46, float %107, float %62, float %134)  ; FMad(a,b,c)
  %136 = fadd fast float %135, %112
  %137 = fmul fast float %126, %98
  %138 = call float @dx.op.tertiary.f32(i32 46, float %103, float %128, float %137)  ; FMad(a,b,c)
  %139 = call float @dx.op.tertiary.f32(i32 46, float %108, float %62, float %138)  ; FMad(a,b,c)
  %140 = fadd fast float %139, %113
  %141 = fmul fast float %126, %99
  %142 = call float @dx.op.tertiary.f32(i32 46, float %104, float %128, float %141)  ; FMad(a,b,c)
  %143 = call float @dx.op.tertiary.f32(i32 46, float %109, float %62, float %142)  ; FMad(a,b,c)
  %144 = fadd fast float %143, %114
  %145 = fdiv fast float %132, %144
  %146 = fdiv fast float %136, %144
  %147 = fdiv fast float %140, %144
  br label %316

; <label>:148                                     ; preds = %26
  %149 = sub i32 %19, %15
  %150 = extractvalue %dx.types.CBufRet.i32 %28, 1
  %151 = icmp ult i32 %149, %150
  br i1 %151, label %152, label %195

; <label>:152                                     ; preds = %148
  %153 = call %dx.types.Handle @"dx.op.createHandleForLib.class.StructuredBuffer<vector<unsigned int, 2> >"(i32 160, %"class.StructuredBuffer<vector<unsigned int, 2> >" %4)  ; CreateHandleForLib(Resource)
  %154 = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %153, i32 %149, i32 0, i8 3, i32 4)  ; RawBufferLoad(srv,index,elementOffset,mask,alignment)
  %155 = extractvalue %dx.types.ResRet.i32 %154, 0
  %156 = extractvalue %dx.types.ResRet.i32 %154, 1
  %157 = lshr i32 %155, 16
  %158 = and i32 %157, 4095
  %159 = lshr i32 %155, 20
  %160 = and i32 %159, 3840
  %161 = lshr i32 %156, 24
  %162 = or i32 %160, %161
  %163 = lshr i32 %156, 12
  %164 = and i32 %163, 4095
  %165 = and i32 %156, 4095
  %166 = uitofp i32 %164 to float
  %167 = uitofp i32 %165 to float
  %168 = fmul fast float %166, 0x3F40010020000000
  %169 = fmul fast float %167, 0x3F40010020000000
  %170 = fadd fast float %168, -1.000000e+00
  %171 = fadd fast float %169, -1.000000e+00
  %172 = call float @dx.op.unary.f32(i32 6, float %170)  ; FAbs(value)
  %173 = call float @dx.op.unary.f32(i32 6, float %171)  ; FAbs(value)
  %174 = call float @dx.op.dot2.f32(i32 54, float 1.000000e+00, float 1.000000e+00, float %172, float %173)  ; Dot2(ax,ay,bx,by)
  %175 = fsub fast float 1.000000e+00, %174
  %176 = fcmp fast olt float %175, 0.000000e+00
  br i1 %176, label %177, label %186

; <label>:177                                     ; preds = %152
  %178 = fsub fast float 1.000000e+00, %173
  %179 = fsub fast float 1.000000e+00, %172
  %180 = fcmp fast oge float %170, 0.000000e+00
  %181 = fcmp fast oge float %171, 0.000000e+00
  %182 = select i1 %180, float 0x3FEFFFEB00000000, float -1.000000e+00
  %183 = select i1 %181, float 0x3FEFFFEB00000000, float -1.000000e+00
  %184 = fmul fast float %178, %182
  %185 = fmul fast float %179, %183
  br label %186

; <label>:186                                     ; preds = %177, %152
  %187 = phi float [ %184, %177 ], [ %170, %152 ]
  %188 = phi float [ %185, %177 ], [ %171, %152 ]
  %189 = call float @dx.op.dot3.f32(i32 55, float %187, float %188, float %175, float %187, float %188, float %175)  ; Dot3(ax,ay,az,bx,by,bz)
  %190 = call float @dx.op.binary.f32(i32 35, float 0x3810000000000000, float %189)  ; FMax(a,b)
  %191 = call float @dx.op.unary.f32(i32 25, float %190)  ; Rsqrt(value)
  %192 = fmul fast float %191, %187
  %193 = fmul fast float %191, %188
  %194 = fmul fast float %191, %175
  br label %195

; <label>:195                                     ; preds = %186, %148
  %196 = phi i32 [ %158, %186 ], [ undef, %148 ]
  %197 = phi i32 [ %162, %186 ], [ undef, %148 ]
  %198 = phi float [ %192, %186 ], [ undef, %148 ]
  %199 = phi float [ %193, %186 ], [ undef, %148 ]
  %200 = phi float [ %194, %186 ], [ undef, %148 ]
  %201 = call %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<vector<float, 4> >"(i32 160, %"class.Texture2D<vector<float, 4> >" %6)  ; CreateHandleForLib(Resource)
  %202 = call %dx.types.ResRet.f32 @dx.op.textureLoad.f32(i32 66, %dx.types.Handle %201, i32 0, i32 %196, i32 %197, i32 undef, i32 undef, i32 undef, i32 undef)  ; TextureLoad(srv,mipLevelOrSampleCount,coord0,coord1,coord2,offset0,offset1,offset2)
  %203 = extractvalue %dx.types.ResRet.f32 %202, 0
  %204 = extractvalue %dx.types.ResRet.f32 %202, 1
  %205 = extractvalue %dx.types.ResRet.f32 %202, 2
  %206 = extractvalue %dx.types.ResRet.f32 %202, 3
  %207 = fmul fast float %203, 2.000000e+00
  %208 = fmul fast float %204, 2.000000e+00
  %209 = fmul fast float %205, 2.000000e+00
  %210 = fadd fast float %207, -1.000000e+00
  %211 = fadd fast float %208, -1.000000e+00
  %212 = fadd fast float %209, -1.000000e+00
  %213 = call float @dx.op.dot3.f32(i32 55, float %210, float %211, float %212, float %210, float %211, float %212)  ; Dot3(ax,ay,az,bx,by,bz)
  %214 = call float @dx.op.binary.f32(i32 35, float 0x3810000000000000, float %213)  ; FMax(a,b)
  %215 = call float @dx.op.unary.f32(i32 25, float %214)  ; Rsqrt(value)
  %216 = fmul fast float %210, %215
  %217 = fmul fast float %211, %215
  %218 = fmul fast float %212, %215
  %219 = fmul fast float %206, 2.550000e+02
  %220 = call float @dx.op.unary.f32(i32 26, float %219)  ; Round_ne(value)
  %221 = fptosi float %220 to i32
  %222 = and i32 %221, 1
  %223 = icmp eq i32 %222, 0
  %224 = call %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<vector<unsigned int, 2> >"(i32 160, %"class.Texture2D<vector<unsigned int, 2> >" %7)  ; CreateHandleForLib(Resource)
  %225 = call %dx.types.ResRet.i32 @dx.op.textureLoad.i32(i32 66, %dx.types.Handle %224, i32 0, i32 %196, i32 %197, i32 undef, i32 undef, i32 undef, i32 undef)  ; TextureLoad(srv,mipLevelOrSampleCount,coord0,coord1,coord2,offset0,offset1,offset2)
  %226 = extractvalue %dx.types.ResRet.i32 %225, 0
  %227 = and i32 %226, 16777215
  %228 = uitofp i32 %227 to double
  %229 = fmul fast double %228, 0x3E70000010000010
  %230 = fptrunc double %229 to float
  %231 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 134)  ; CBufferLoadLegacy(handle,regIndex)
  %232 = extractvalue %dx.types.CBufRet.f32 %231, 0
  %233 = extractvalue %dx.types.CBufRet.f32 %231, 1
  %234 = extractvalue %dx.types.CBufRet.f32 %231, 2
  %235 = extractvalue %dx.types.CBufRet.f32 %231, 3
  %236 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 135)  ; CBufferLoadLegacy(handle,regIndex)
  %237 = extractvalue %dx.types.CBufRet.f32 %236, 0
  %238 = extractvalue %dx.types.CBufRet.f32 %236, 1
  %239 = extractvalue %dx.types.CBufRet.f32 %236, 2
  %240 = extractvalue %dx.types.CBufRet.f32 %236, 3
  %241 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 136)  ; CBufferLoadLegacy(handle,regIndex)
  %242 = extractvalue %dx.types.CBufRet.f32 %241, 0
  %243 = extractvalue %dx.types.CBufRet.f32 %241, 1
  %244 = extractvalue %dx.types.CBufRet.f32 %241, 2
  %245 = extractvalue %dx.types.CBufRet.f32 %241, 3
  %246 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 137)  ; CBufferLoadLegacy(handle,regIndex)
  %247 = extractvalue %dx.types.CBufRet.f32 %246, 0
  %248 = extractvalue %dx.types.CBufRet.f32 %246, 1
  %249 = extractvalue %dx.types.CBufRet.f32 %246, 2
  %250 = extractvalue %dx.types.CBufRet.f32 %246, 3
  %251 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 202)  ; CBufferLoadLegacy(handle,regIndex)
  %252 = extractvalue %dx.types.CBufRet.f32 %251, 2
  %253 = extractvalue %dx.types.CBufRet.f32 %251, 3
  %254 = sitofp i32 %196 to float
  %255 = sitofp i32 %197 to float
  %256 = fadd fast float %254, 5.000000e-01
  %257 = fadd fast float %255, 5.000000e-01
  %258 = fmul fast float %256, 2.000000e+00
  %259 = fmul fast float %258, %252
  %260 = fmul fast float %257, 2.000000e+00
  %261 = fmul fast float %260, %253
  %262 = fadd fast float %259, -1.000000e+00
  %263 = fadd fast float %261, -1.000000e+00
  %264 = fsub fast float -0.000000e+00, %263
  %265 = fmul fast float %262, %232
  %266 = call float @dx.op.tertiary.f32(i32 46, float %237, float %264, float %265)  ; FMad(a,b,c)
  %267 = call float @dx.op.tertiary.f32(i32 46, float %242, float %230, float %266)  ; FMad(a,b,c)
  %268 = fadd fast float %267, %247
  %269 = fmul fast float %262, %233
  %270 = call float @dx.op.tertiary.f32(i32 46, float %238, float %264, float %269)  ; FMad(a,b,c)
  %271 = call float @dx.op.tertiary.f32(i32 46, float %243, float %230, float %270)  ; FMad(a,b,c)
  %272 = fadd fast float %271, %248
  %273 = fmul fast float %262, %234
  %274 = call float @dx.op.tertiary.f32(i32 46, float %239, float %264, float %273)  ; FMad(a,b,c)
  %275 = call float @dx.op.tertiary.f32(i32 46, float %244, float %230, float %274)  ; FMad(a,b,c)
  %276 = fadd fast float %275, %249
  %277 = fmul fast float %262, %235
  %278 = call float @dx.op.tertiary.f32(i32 46, float %240, float %264, float %277)  ; FMad(a,b,c)
  %279 = call float @dx.op.tertiary.f32(i32 46, float %245, float %230, float %278)  ; FMad(a,b,c)
  %280 = fadd fast float %279, %250
  %281 = fdiv fast float %268, %280
  %282 = fdiv fast float %272, %280
  %283 = fdiv fast float %276, %280
  br i1 %223, label %316, label %284

; <label>:284                                     ; preds = %195
  %285 = call %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<float>"(i32 160, %"class.Texture2D<float>" %2)  ; CreateHandleForLib(Resource)
  %286 = call %dx.types.ResRet.f32 @dx.op.textureLoad.f32(i32 66, %dx.types.Handle %285, i32 0, i32 %196, i32 %197, i32 undef, i32 undef, i32 undef, i32 undef)  ; TextureLoad(srv,mipLevelOrSampleCount,coord0,coord1,coord2,offset0,offset1,offset2)
  %287 = extractvalue %dx.types.ResRet.f32 %286, 0
  %288 = call float @dx.op.tertiary.f32(i32 46, float %242, float %287, float %266)  ; FMad(a,b,c)
  %289 = fadd fast float %288, %247
  %290 = call float @dx.op.tertiary.f32(i32 46, float %243, float %287, float %270)  ; FMad(a,b,c)
  %291 = fadd fast float %290, %248
  %292 = call float @dx.op.tertiary.f32(i32 46, float %244, float %287, float %274)  ; FMad(a,b,c)
  %293 = fadd fast float %292, %249
  %294 = call float @dx.op.tertiary.f32(i32 46, float %245, float %287, float %278)  ; FMad(a,b,c)
  %295 = fadd fast float %294, %250
  %296 = fdiv fast float %289, %295
  %297 = fdiv fast float %291, %295
  %298 = fdiv fast float %293, %295
  %299 = call %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<vector<float, 4> >"(i32 160, %"class.Texture2D<vector<float, 4> >" %1)  ; CreateHandleForLib(Resource)
  %300 = call %dx.types.ResRet.f32 @dx.op.textureLoad.f32(i32 66, %dx.types.Handle %299, i32 0, i32 %196, i32 %197, i32 undef, i32 undef, i32 undef, i32 undef)  ; TextureLoad(srv,mipLevelOrSampleCount,coord0,coord1,coord2,offset0,offset1,offset2)
  %301 = extractvalue %dx.types.ResRet.f32 %300, 0
  %302 = extractvalue %dx.types.ResRet.f32 %300, 1
  %303 = extractvalue %dx.types.ResRet.f32 %300, 2
  %304 = fmul fast float %301, 2.000000e+00
  %305 = fmul fast float %302, 2.000000e+00
  %306 = fmul fast float %303, 2.000000e+00
  %307 = fadd fast float %304, -1.000000e+00
  %308 = fadd fast float %305, -1.000000e+00
  %309 = fadd fast float %306, -1.000000e+00
  %310 = call float @dx.op.dot3.f32(i32 55, float %307, float %308, float %309, float %307, float %308, float %309)  ; Dot3(ax,ay,az,bx,by,bz)
  %311 = call float @dx.op.binary.f32(i32 35, float 0x3810000000000000, float %310)  ; FMax(a,b)
  %312 = call float @dx.op.unary.f32(i32 25, float %311)  ; Rsqrt(value)
  %313 = fmul fast float %307, %312
  %314 = fmul fast float %308, %312
  %315 = fmul fast float %309, %312
  br label %316

; <label>:316                                     ; preds = %284, %195, %86, %29
  %317 = phi float [ %145, %86 ], [ 0.000000e+00, %29 ], [ %296, %284 ], [ %281, %195 ]
  %318 = phi float [ %146, %86 ], [ 0.000000e+00, %29 ], [ %297, %284 ], [ %282, %195 ]
  %319 = phi float [ %147, %86 ], [ 0.000000e+00, %29 ], [ %298, %284 ], [ %283, %195 ]
  %320 = phi float [ %92, %86 ], [ 0.000000e+00, %29 ], [ %198, %284 ], [ %198, %195 ]
  %321 = phi float [ %93, %86 ], [ 0.000000e+00, %29 ], [ %199, %284 ], [ %199, %195 ]
  %322 = phi float [ %94, %86 ], [ 0.000000e+00, %29 ], [ %200, %284 ], [ %200, %195 ]
  %323 = phi float [ %52, %86 ], [ 0.000000e+00, %29 ], [ %313, %284 ], [ %216, %195 ]
  %324 = phi float [ %53, %86 ], [ 0.000000e+00, %29 ], [ %314, %284 ], [ %217, %195 ]
  %325 = phi float [ %54, %86 ], [ 0.000000e+00, %29 ], [ %315, %284 ], [ %218, %195 ]
  %326 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 30)  ; CBufferLoadLegacy(handle,regIndex)
  %327 = extractvalue %dx.types.CBufRet.f32 %326, 0
  %328 = extractvalue %dx.types.CBufRet.f32 %326, 1
  %329 = extractvalue %dx.types.CBufRet.f32 %326, 2
  %330 = fsub fast float %327, %317
  %331 = fsub fast float %328, %318
  %332 = fsub fast float %329, %319
  %333 = fmul fast float %330, %330
  %334 = fmul fast float %331, %331
  %335 = fadd fast float %333, %334
  %336 = fmul fast float %332, %332
  %337 = fadd fast float %335, %336
  %338 = call float @dx.op.unary.f32(i32 24, float %337)  ; Sqrt(value)
  %339 = call float @dx.op.binary.f32(i32 35, float %338, float 0x3F50624DE0000000)  ; FMax(a,b)
  %340 = fdiv fast float 1.000000e+00, %339
  %341 = fmul fast float %340, %330
  %342 = fmul fast float %340, %331
  %343 = fmul fast float %340, %332
  %344 = call float @dx.op.dot3.f32(i32 55, float %341, float %342, float %343, float %323, float %324, float %325)  ; Dot3(ax,ay,az,bx,by,bz)
  %345 = fmul fast float %344, %323
  %346 = fmul fast float %344, %324
  %347 = fmul fast float %344, %325
  %348 = fsub fast float %341, %345
  %349 = fsub fast float %342, %346
  %350 = fsub fast float %343, %347
  %351 = call float @dx.op.dot3.f32(i32 55, float %348, float %349, float %350, float %348, float %349, float %350)  ; Dot3(ax,ay,az,bx,by,bz)
  %352 = call float @dx.op.binary.f32(i32 35, float 0x3810000000000000, float %351)  ; FMax(a,b)
  %353 = call float @dx.op.unary.f32(i32 25, float %352)  ; Rsqrt(value)
  %354 = fmul fast float %353, %348
  %355 = fmul fast float %353, %349
  %356 = fmul fast float %353, %350
  %357 = fadd fast float %354, %323
  %358 = fadd fast float %355, %324
  %359 = fadd fast float %356, %325
  %360 = call float @dx.op.dot3.f32(i32 55, float %357, float %358, float %359, float %357, float %358, float %359)  ; Dot3(ax,ay,az,bx,by,bz)
  %361 = call float @dx.op.binary.f32(i32 35, float 0x3810000000000000, float %360)  ; FMax(a,b)
  %362 = call float @dx.op.unary.f32(i32 25, float %361)  ; Rsqrt(value)
  %363 = fmul fast float %362, %357
  %364 = fmul fast float %362, %358
  %365 = fmul fast float %362, %359
  %366 = call float @dx.op.dot3.f32(i32 55, float %320, float %321, float %322, float %323, float %324, float %325)  ; Dot3(ax,ay,az,bx,by,bz)
  %367 = call float @dx.op.unary.f32(i32 7, float %366)  ; Saturate(value)
  %368 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %12, i32 205)  ; CBufferLoadLegacy(handle,regIndex)
  %369 = extractvalue %dx.types.CBufRet.f32 %368, 0
  %370 = fmul fast float %369, 8.000000e+00
  %371 = fmul fast float %369, -7.000000e+00
  %372 = fmul fast float %371, %367
  %373 = fadd fast float %372, %370
  %374 = fmul fast float %338, 2.500000e-01
  %375 = call float @dx.op.binary.f32(i32 35, float %374, float 0x3FC99999A0000000)  ; FMax(a,b)
  %376 = call float @dx.op.binary.f32(i32 36, float %375, float 1.000000e+01)  ; FMin(a,b)
  %377 = fmul fast float %363, %376
  %378 = fmul fast float %377, %373
  %379 = fmul fast float %364, %376
  %380 = fmul fast float %379, %373
  %381 = fmul fast float %365, %376
  %382 = fmul fast float %381, %373
  %383 = fadd fast float %378, %317
  %384 = fadd fast float %380, %318
  %385 = fadd fast float %382, %319
  %386 = call float @dx.op.binary.f32(i32 35, float %383, float 0xC415AF1D80000000)  ; FMax(a,b)
  %387 = call float @dx.op.binary.f32(i32 35, float %384, float 0xC415AF1D80000000)  ; FMax(a,b)
  %388 = call float @dx.op.binary.f32(i32 35, float %385, float 0xC415AF1D80000000)  ; FMax(a,b)
  %389 = call float @dx.op.binary.f32(i32 36, float %386, float 0x4415AF1D80000000)  ; FMin(a,b)
  %390 = call float @dx.op.binary.f32(i32 36, float %387, float 0x4415AF1D80000000)  ; FMin(a,b)
  %391 = call float @dx.op.binary.f32(i32 36, float %388, float 0x4415AF1D80000000)  ; FMin(a,b)
  %392 = select i1 %27, float 6.400000e+01, float 4.096000e+03
  %393 = getelementptr inbounds %struct.RayIntersection_RT, %struct.RayIntersection_RT* %11, i32 0, i32 0
  %394 = getelementptr inbounds %struct.RayIntersection_RT, %struct.RayIntersection_RT* %11, i32 0, i32 1
  store i32 0, i32* %394, align 4
  %395 = getelementptr inbounds %struct.RayIntersection_RT, %struct.RayIntersection_RT* %11, i32 0, i32 2
  %396 = getelementptr inbounds %struct.RayIntersection_RT, %struct.RayIntersection_RT* %11, i32 0, i32 3
  store i32 0, i32* %396, align 4
  %397 = getelementptr inbounds %struct.RayIntersection_RT, %struct.RayIntersection_RT* %11, i32 0, i32 4
  store i32 0, i32* %397, align 4
  %398 = getelementptr inbounds %struct.RayIntersection_RT, %struct.RayIntersection_RT* %11, i32 0, i32 5
  store i32 0, i32* %398, align 4
  store float %392, float* %393, align 4, !tbaa !54
  store i32 1, i32* %395, align 4, !tbaa !58
  %399 = select i1 %27, i32 1, i32 2
  %400 = select i1 %27, i32 656, i32 0
  %401 = call %dx.types.Handle @dx.op.createHandleForLib.struct.RaytracingAccelerationStructure(i32 160, %struct.RaytracingAccelerationStructure %8)  ; CreateHandleForLib(Resource)
  call void @dx.op.traceRay.struct.RayIntersection_RT(i32 157, %dx.types.Handle %401, i32 %400, i32 %399, i32 0, i32 1, i32 0, float %389, float %390, float %391, float 0x3F50624DE0000000, float %320, float %321, float %322, float %392, %struct.RayIntersection_RT* nonnull %11)  ; TraceRay(AccelerationStructure,RayFlags,InstanceInclusionMask,RayContributionToHitGroupIndex,MultiplierForGeometryContributionToShaderIndex,MissShaderIndex,Origin_X,Origin_Y,Origin_Z,TMin,Direction_X,Direction_Y,Direction_Z,TMax,payload)
  %402 = call %dx.types.CBufRet.i32 @dx.op.cbufferLoadLegacy.i32(i32 59, %dx.types.Handle %12, i32 289)  ; CBufferLoadLegacy(handle,regIndex)
  %403 = extractvalue %dx.types.CBufRet.i32 %402, 2
  %404 = icmp ult i32 %19, %403
  br i1 %404, label %405, label %414

; <label>:405                                     ; preds = %316
  %406 = load float, float* %393, align 4, !tbaa !54
  %407 = bitcast float %406 to i32
  %408 = load i32, i32* %394, align 4, !tbaa !58
  %409 = load i32, i32* %395, align 4, !tbaa !58
  %410 = load i32, i32* %396, align 4, !tbaa !58
  %411 = load i32, i32* %397, align 4, !tbaa !58
  %412 = load i32, i32* %398, align 4, !tbaa !58
  %413 = call %dx.types.Handle @"dx.op.createHandleForLib.class.RWStructuredBuffer<RayIntersection_Data>"(i32 160, %"class.RWStructuredBuffer<RayIntersection_Data>" %9)  ; CreateHandleForLib(Resource)
  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 0, i32 %407, i32 %408, i32 %409, i32 %410, i8 15, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)
  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 16, i32 %411, i32 undef, i32 undef, i32 undef, i8 1, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)
  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 20, i32 %412, i32 undef, i32 undef, i32 undef, i8 1, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)
  br label %414

; <label>:414                                     ; preds = %405, %316, %0
  ret void
}

; Function Attrs: nounwind

; Function Attrs: nounwind
define void @"\01?Miss@@YAXURayIntersection_RT@@@Z"(%struct.RayIntersection_RT* noalias nocapture %rayIntersection) #0 {
  ret void
}

; Function Attrs: nounwind readnone
declare float @dx.op.unary.f32(i32, float) #1

; Function Attrs: nounwind readnone
declare float @dx.op.dot2.f32(i32, float, float, float, float) #1

; Function Attrs: nounwind readnone
declare float @dx.op.dot3.f32(i32, float, float, float, float, float, float) #1

; Function Attrs: nounwind readnone
declare float @dx.op.binary.f32(i32, float, float) #1

; Function Attrs: nounwind readnone
declare float @dx.op.tertiary.f32(i32, float, float, float) #1

; Function Attrs: nounwind readonly
declare %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32, %dx.types.Handle, i32, i32, i8, i32) #2

; Function Attrs: nounwind readonly
declare %dx.types.ResRet.f32 @dx.op.textureLoad.f32(i32, %dx.types.Handle, i32, i32, i32, i32, i32, i32, i32) #2

; Function Attrs: nounwind readonly
declare %dx.types.ResRet.i32 @dx.op.textureLoad.i32(i32, %dx.types.Handle, i32, i32, i32, i32, i32, i32, i32) #2

; Function Attrs: nounwind
declare void @dx.op.traceRay.struct.RayIntersection_RT(i32, %dx.types.Handle, i32, i32, i32, i32, i32, float, float, float, float, float, float, float, float, %struct.RayIntersection_RT*) #0

; Function Attrs: nounwind readnone
declare i32 @dx.op.dispatchRaysIndex.i32(i32, i8) #1

; Function Attrs: nounwind
declare void @dx.op.rawBufferStore.i32(i32, %dx.types.Handle, i32, i32, i32, i32, i32, i32, i8, i32) #0

; Function Attrs: nounwind readonly
declare %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32, %dx.types.Handle, i32) #2

; Function Attrs: nounwind readonly
declare %dx.types.CBufRet.i32 @dx.op.cbufferLoadLegacy.i32(i32, %dx.types.Handle, i32) #2

; Function Attrs: nounwind readonly
declare %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<vector<float, 4> >"(i32, %"class.Texture2D<vector<float, 4> >") #2

; Function Attrs: nounwind readonly
declare %dx.types.Handle @"dx.op.createHandleForLib.class.StructuredBuffer<unsigned int>"(i32, %"class.StructuredBuffer<unsigned int>") #2

; Function Attrs: nounwind readonly
declare %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<vector<unsigned int, 2> >"(i32, %"class.Texture2D<vector<unsigned int, 2> >") #2

; Function Attrs: nounwind readonly
declare %dx.types.Handle @"dx.op.createHandleForLib.class.Texture2D<float>"(i32, %"class.Texture2D<float>") #2

; Function Attrs: nounwind readonly
declare %dx.types.Handle @"dx.op.createHandleForLib.class.StructuredBuffer<vector<unsigned int, 2> >"(i32, %"class.StructuredBuffer<vector<unsigned int, 2> >") #2

; Function Attrs: nounwind readonly
declare %dx.types.Handle @dx.op.createHandleForLib.struct.RaytracingAccelerationStructure(i32, %struct.RaytracingAccelerationStructure) #2

; Function Attrs: nounwind readonly

; Function Attrs: nounwind readonly
declare %dx.types.Handle @"dx.op.createHandleForLib.class.RWStructuredBuffer<RayIntersection_Data>"(i32, %"class.RWStructuredBuffer<RayIntersection_Data>") #2

; Function Attrs: nounwind readonly
declare %dx.types.Handle @"dx.op.createHandleForLib.hostlayout.$Globals"(i32, %"hostlayout.$Globals") #2

attributes #0 = { nounwind }
attributes #1 = { nounwind readnone }
attributes #2 = { nounwind readonly }

!llvm.ident = !{!0}
!dx.version = !{!1}
!dx.valver = !{!2}
!dx.shaderModel = !{!3}
!dx.resources = !{!4}
!dx.typeAnnotations = !{!25}
!dx.entryPoints = !{!31, !34, !37}

!0 = !{!"dxcoob 1.7.2212.40 (e043f4a12)"}
!1 = !{i32 1, i32 5}
!2 = !{i32 1, i32 7}
!3 = !{!"lib", i32 6, i32 5}
!4 = !{!5, !19, !23, null}
!5 = !{!6, !8, !10, !12, !14, !16, !17, !18}
!6 = !{i32 0, %struct.RaytracingAccelerationStructure* @"\01?_RaytracingAccelerationStructure@@3URaytracingAccelerationStructure@@A", !"_RaytracingAccelerationStructure", i32 0, i32 0, i32 1, i32 16, i32 0, !7}
!7 = !{i32 0, i32 4}
!8 = !{i32 1, %"class.Texture2D<vector<unsigned int, 2> >"* @"\01?_PackedRayInfo0@@3V?$Texture2D@V?$vector@I$01@@@@A", !"_PackedRayInfo0", i32 0, i32 1, i32 1, i32 2, i32 0, !9}
!9 = !{i32 0, i32 5}
!10 = !{i32 2, %"class.Texture2D<vector<float, 4> >"* @"\01?_SceneNormal@@3V?$Texture2D@V?$vector@M$03@@@@A", !"_SceneNormal", i32 0, i32 2, i32 1, i32 2, i32 0, !11}
!11 = !{i32 0, i32 9}
!12 = !{i32 3, %"class.StructuredBuffer<unsigned int>"* @"\01?_RayPixelIdBuffer@@3V?$StructuredBuffer@I@@A", !"_RayPixelIdBuffer", i32 0, i32 3, i32 1, i32 12, i32 0, !13}
!13 = !{i32 1, i32 4}
!14 = !{i32 4, %"class.StructuredBuffer<vector<unsigned int, 2> >"* @"\01?_PackedSpecRayInfoBuffer@@3V?$StructuredBuffer@V?$vector@I$01@@@@A", !"_PackedSpecRayInfoBuffer", i32 0, i32 4, i32 1, i32 12, i32 0, !15}
!15 = !{i32 1, i32 8}
!16 = !{i32 5, %"class.StructuredBuffer<unsigned int>"* @"\01?_RayAllocatorBuffer@@3V?$StructuredBuffer@I@@A", !"_RayAllocatorBuffer", i32 0, i32 5, i32 1, i32 12, i32 0, !13}
!17 = !{i32 6, %"class.Texture2D<float>"* @"\01?_SceneForwardDepth@@3V?$Texture2D@M@@A", !"_SceneForwardDepth", i32 0, i32 6, i32 1, i32 2, i32 0, !11}
!18 = !{i32 7, %"class.Texture2D<vector<float, 4> >"* @"\01?_SceneForwardNormal@@3V?$Texture2D@V?$vector@M$03@@@@A", !"_SceneForwardNormal", i32 0, i32 7, i32 1, i32 2, i32 0, !11}
!19 = !{!21}
!21 = !{i32 0, %"class.RWStructuredBuffer<RayIntersection_Data>"* @"\01?_RWRayHitBuffer@@3V?$RWStructuredBuffer@URayIntersection_Data@@@@A", !"_RWRayHitBuffer", i32 0, i32 1, i32 1, i32 12, i1 false, i1 false, i1 false, !22}
!22 = !{i32 1, i32 24}
!23 = !{!24}
!24 = !{i32 0, %"hostlayout.$Globals"* @"$Globals_legacy", !"$Globals", i32 0, i32 0, i32 1, i32 4636, null}
!25 = !{i32 1, void ()* @"\01?ExecuteTrace@@YAXXZ", !26, void (%struct.RayIntersection_RT*)* @"\01?Miss@@YAXURayIntersection_RT@@@Z", !29}
!26 = !{!27}
!27 = !{i32 1, !28, !28}
!28 = !{}
!29 = !{!27, !30}
!30 = !{i32 2, !28, !28}
!31 = !{null, !"", null, !4, !32}
!32 = !{i32 0, i64 65620, i32 5, !33}
!33 = !{i32 0}
!34 = !{void ()* @"\01?ExecuteTrace@@YAXXZ", !"\01?ExecuteTrace@@YAXXZ", null, null, !35}
!35 = !{i32 8, i32 7, i32 5, !33}
!37 = !{void (%struct.RayIntersection_RT*)* @"\01?Miss@@YAXURayIntersection_RT@@@Z", !"\01?Miss@@YAXURayIntersection_RT@@@Z", null, null, !38}
!38 = !{i32 8, i32 11, i32 6, i32 24, i32 5, !33}
!39 = !{!40}
!40 = distinct !{!40, !41, !"\01?CorrectRay@@YAXURayInfo@@V?$vector@I$01@@@Z: %info"}
!41 = distinct !{!41, !"\01?CorrectRay@@YAXURayInfo@@V?$vector@I$01@@@Z"}
!42 = !{!43, !45}
!43 = distinct !{!43, !44, !"\01?GetSpecRay@@YAMIAIAV?$vector@I$01@@AIAV?$vector@M$02@@@Z: %pixelId"}
!44 = distinct !{!44, !"\01?GetSpecRay@@YAMIAIAV?$vector@I$01@@AIAV?$vector@M$02@@@Z"}
!45 = distinct !{!45, !44, !"\01?GetSpecRay@@YAMIAIAV?$vector@I$01@@AIAV?$vector@M$02@@@Z: %dir"}
!46 = !{!47, !49}
!47 = distinct !{!47, !48, !"\01?GetRay@@YA?AURayInfo@@IAIAV?$vector@I$01@@@Z: %agg.result"}
!48 = distinct !{!48, !"\01?GetRay@@YA?AURayInfo@@IAIAV?$vector@I$01@@@Z"}
!49 = distinct !{!49, !48, !"\01?GetRay@@YA?AURayInfo@@IAIAV?$vector@I$01@@@Z: %pixelId"}
!50 = !{!51, !47, !49}
!51 = distinct !{!51, !52, !"\01?GetRay@@YA?AURayInfo@@V?$vector@I$01@@@Z: %agg.result"}
!52 = distinct !{!52, !"\01?GetRay@@YA?AURayInfo@@V?$vector@I$01@@@Z"}
!53 = distinct !{!53, !"dx.controlflow.hints", i32 1}
!54 = !{!55, !55, i64 0}
!55 = !{!"float", !56, i64 0}
!56 = !{!"omnipotent char", !57, i64 0}
!57 = !{!"Simple C/C++ TBAA"}
!58 = !{!59, !59, i64 0}
!59 = !{!"int", !56, i64 0}
!60 = !{!61}
!61 = distinct !{!61, !62, !"\01?CorrectRay@@YAXURayInfo@@V?$vector@I$01@@@Z: %info"}
!62 = distinct !{!62, !"\01?CorrectRay@@YAXURayInfo@@V?$vector@I$01@@@Z"}
!63 = !{!64, !66}
!64 = distinct !{!64, !65, !"\01?GetSpecRay@@YAMIAIAV?$vector@I$01@@AIAV?$vector@M$02@@@Z: %pixelId"}
!65 = distinct !{!65, !"\01?GetSpecRay@@YAMIAIAV?$vector@I$01@@AIAV?$vector@M$02@@@Z"}
!66 = distinct !{!66, !65, !"\01?GetSpecRay@@YAMIAIAV?$vector@I$01@@AIAV?$vector@M$02@@@Z: %dir"}
!67 = !{!68, !70}
!68 = distinct !{!68, !69, !"\01?GetRay@@YA?AURayInfo@@IAIAV?$vector@I$01@@@Z: %agg.result"}
!69 = distinct !{!69, !"\01?GetRay@@YA?AURayInfo@@IAIAV?$vector@I$01@@@Z"}
!70 = distinct !{!70, !69, !"\01?GetRay@@YA?AURayInfo@@IAIAV?$vector@I$01@@@Z: %pixelId"}
!71 = !{!72, !68, !70}
!72 = distinct !{!72, !73, !"\01?GetRay@@YA?AURayInfo@@V?$vector@I$01@@@Z: %agg.result"}
!73 = distinct !{!73, !"\01?GetRay@@YA?AURayInfo@@V?$vector@I$01@@@Z"}
