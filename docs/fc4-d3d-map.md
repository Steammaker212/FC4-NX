# Far Cry 4's Direct3D for Renut's renderer: hook map and device layout (2026-11-09)

Read-only analysis of `out/renut_image.bin` (game.xex, XDK 2.0.21256). Nothing in Renut's sources was changed. The full
table is `out/fc4_d3d/hook_map.txt` (398 rows): one row per hook line in `app/src/renut_engine/gpu/d3d/hooks/*.cpp`
(katamari-nx's addresses today), plus sa2-nx's extra hooks and the helpers sa2-nx names. Each row gives the FC4 address,
SA2's address, a confidence and the evidence. The device layout check is `out/fc4_d3d/offsets_check.txt`.

**In short:** FC4's Direct3D is SA2's (2.0.21076). The device is 0x6080 bytes, every SA2 device offset checked is at
the same value, and the functions have SA2's exact sizes and order inside each object. Use **sa2-nx's** hook set and
device offsets. Only the addresses change.

## Results

| | Count |
|---|---|
| Hook lines in the tree (hooked / `BANJO_RENUT_UNHOOKED`) | 322 / 34 |
| ... found in FC4, high confidence | 266 (222 of them from the state tables) |
| ... medium / low | 43 / 8 |
| ... not found (each with its reason in the map) | 39 (16 of them hooked in the tree) |
| sa2-nx's own hook table (15 rows, 24 functions) | **23 of 24 found**; DrawVerticesUP is not linked in FC4 |

### sa2-nx's hooks at FC4's addresses

| Function | FC4 | SA2 | Evidence (short) |
|---|---|---|---|
| Direct3D_CreateDevice | **83F18AB0** | 8254FC10 | the only `li r3,0x6080`; type 2: 0x80 into +11068; BehaviorFlags +24392 |
| CDevice::KickOff / KickOffSegment | **83F2EE78** / **83F2EAF0** | 8254EBB8 / 8254E830 | shift 0x19E02C0 (ring object); KickOff calls KickOffSegment; InKickOff +13600 |
| BeginRingBig, ring segment allocator | **83F2F0B8**, **83F2DD50** | 8254EDF8, 8254DA90 | shift 0x19E02C0; BeginRingBig = KickOff + segment allocator; Swap calls both |
| RingBufferDeviceAllocate, AllocateInlineData | **83F2D820** (medium), **83F2DC68** | 8254D4B8, 8254D9A8 | shifts 0x19E0368 / 0x19E02C0; AllocateInlineData reads CommandBuffer +13920 |
| SetRingBufferParameters | **83F2F200** | 8254EF40 | the only VdInitializeRingBuffer / VdEnableRingBufferRPtrWriteBack caller |
| CDevice::BlockOnFence, CBlocker::Check, IsFencePending | **83F2DA50**, **83F180F8** (medium), **83F2EFB8** | 8254D6E8, 8254F400, 8254ECF8 | BlockOnFence tests +13600 and polls 83F18000 / 83F180F8 / 83F18030; Check reads the 5000 ms global 0x84174F70; IsFencePending goes through VdGlobalDevice and kicks the current fence |
| InsertCallback | **83F2F1A8** | 8254EEE8 | shift 0x19E02C0; 4 game callers |
| SynchronizeToPresentationInterval | **83F199B8** | 825589D8 | Sync to Swap is 0x4C0 in both games; Present calls it |
| Swap | **83F19E78** | 82558E98 | the only VdSwap caller; SwapCount +16968, PresentFenceTag +15344 |
| DrawVertices, DrawIndexedVertices, BeginVertices | **83F28860**, **83F28C78**, **83F283A0** | 82565C60, 82566078, 82565758 | DrawVertices to DrawIndexedVertices is 0x418 in both; BeginVertices stores VerticesRingEnd +13844 |
| DrawVerticesUP | **not linked** | 82565C18 | SA2 has it (18 ins) between BeginVertices and DrawVertices; in FC4 BeginVertices ends at 83F2885C and DrawVertices starts at 83F28860 |
| ClearF (and Clear) | **83F1B838** (83F1B970) | 82563978 (82563AB0) | shift 0x19B7EC0 (6 of 7 clear-chain addresses); ClearF to Clear is 0x138 in both |
| Resolve | **83F2D358** | 825656F8 | the resolve core 83F2C200 to Resolve is 0x1158 in both; 16 game callers + Present |
| XGRegisterVertexShader / PixelShader | **83F24648** / **83F23DA8** | 8255E658 / 8255DBF8 | SA2's sizes (62 / 14 ins); the game's shader wrapper (827B35EC-827B3654) calls XGSet*ShaderHeader (83F24608 / 83F245D0) and then these. Shader objects: 0x368 bytes for vertex shaders (memset 872), pixel shader container at +0x28 |
| CreateVertexDeclaration | **83F24308** (medium) | 8255E198 | one game caller; allocates and builds the declaration |
| D3DResource_Destroy | **83F1C900** | 8254A200 | shift 0x19D2700 from the "is it bound" test (825498C8 to **83F1BFD0**, which loads exactly +12240/12812/12816/12832/13068/13072); BlockOnFence and frees; D3DResource_Release 83F1CBA8 is its only caller |

What sa2-nx's creation hook calls in SA2, in FC4: InitializePresentationParameters **83F36BC0** (8255CB20),
InitializeApiState **83F361F0** (8255C150), the hardware path **83F36E40** (8255CDA0), the device block
**83F368A8** / **83F36918** (8255C808 / 8255C878), XenonGpu_Initialize **83F3CBC8**, the side-buffer ring
**83F2D3A8** (8254D040), CDevice::Uninitialize **83F369E8**, Present **83F1A5E0**, SetGammaRamp **83F21FE8**
(825527D8; ramp at +15408), the flip **83F18FB0** (82557FC0, medium).

### Guest data

| What | FC4 | SA2 (sa2-nx) | Evidence |
|---|---|---|---|
| VdGlobalDevice import slot | **0x82000A9C** (holds 0xFFCAE000) | 0x82000710 | IsFencePending, D3DDevice_BlockOnFence, Destroy and the hardware path read it after KeGetCurrentProcessType (0x82000A98 = the system process's, 0xFFCAD000) |
| XDK build qword (device +11008) | **0x84175650** = 0x0002000053084000 (2.0.21256.0) | 0x82980268 | the device block 83F368A8: `lis 0x8417; ld 22096` then `std +11008` |
| Render / sampler state tables | **0x84174F78** (101) / **0x84175438** (20) | - | {getter, setter, default} at stride 12, the same counts as N&B's and Katamari's; defaults as N&B's (ZEnable 1, ZFunc 3, CullMode 6, BlendFactor FFFFFFFF, ColorWriteEnable 0xF x4, MultiSampleMask 0xFFFF) |
| D3DCAPS9 | **0x822969C0** | - | GetDeviceCaps 83F24790: memcpy(out, it, 304) |
| HiZ owner | **0x842DACD0** | - | CreateSurface 83F1F068 and Destroy 83F1C900 |
| GPU hang time | 0x84174F70 = 5000 (ms) | - | CBlocker::Check |
| Side buffer | 0x12C0 bytes at +17136 | same | the device block: XPhysicalAlloc(4800, 0xB5800000) |

## Method (`tools/fc4_d3d/`)

1. **The hooks to place:** `list_hooks.py` reads the tree's 356 hook lines and sa2-nx's hook blocks
   (`out/fc4_d3d/hooks_list.txt`).
2. **State tables:** `state_tables.py`, and a scan for runs of {code, code, data} records. Many getters and setters
   have no `.pdata` entry, so `.pdata` starts alone miss them. The run at 0x84174F78 is 101 records and the one at
   0x84175438 is 20. Entries 0-9 share the getter 82BF6A08 (`return 0`), as N&B's do. Each of the 222 state hooks
   takes record *i* (`make_map.py`).
3. **SA2 shifts:** `sa2_shift.py`. FC4 and SA2 link the same Direct3D objects. Inside an object, FC4's functions
   have SA2's exact sizes and order; the unused ones are dropped and the objects are ordered differently. For each SA2
   address named in sa2-nx's sources, the tool picks the shift (FC4 - SA2) that puts the most nearby SA2 addresses on
   FC4 function starts. The dense setter and getter area (83F1F900-83F21C00) is left out, because it matches any
   shift. Accepted runs: 0x19E02C0 / 0x19E0368 (ring), 0x19DDBA0 (draw-time flush, 11 of 11), 0x19DA0A0 (device
   creation), 0x19CF810 (setters), 0x19C7C60 (resolve), 0x19C61B0 (shaders), 0x19C2C48 / 0x19C2C00 (draws),
   0x19C0FE0 (swap), 0x19B7EC0 (clear). In each run at least one function was checked by its code.
4. **Katamari's order:** the texture and resource objects (no SA2 addresses there) follow katamari-nx's hook order.
   The evidence is equal sizes: Katamari's size from its adjacent hook addresses against FC4's .pdata size. For
   example Get2DSurfaceDesc / Get3DSurfaceDesc are 64 / 64, Lock2DSurface 36, GetSurfaceLevel 46, CreateTexture 72,
   Surface_GetDesc 38, CreateVertexBuffer 50, BlockSizeOfGpuFormat 38, AlignTextureDimensions 72 and
   GetMipTailLevelOffsetCoords 86. These are "medium".
5. **Checks by code:** fields stored or loaded, imports called (`imports.txt`, from the generated `renut_register.cpp`),
   callers (`fc4lib.callers`), and data references. `fdis.py` prints functions, `summary.py` / `cond.py` summarise a
   range (`out/fc4_d3d/funcs_summary.txt`).
6. `fc4_hook_map_hand.txt` holds every non-table identification with its evidence. `make_map.py` writes
   `out/fc4_d3d/hook_map.txt`.

## Not found or not linked (reasons in the map)

- **Not linked in FC4:** DrawVerticesUP (see above), CreateVertexShader / CreatePixelShader (the game uses
  XGSet*ShaderHeader + XGRegister*, so Renut's XGRegister hooks see every shader), Lock3DSurface and
  D3DVolume_LockBox (nothing in their slots).
- **Not identified in this pass (tree-hooked):** BeginRingManual, D3DResource_GetType, D3DConstantBuffer_Unlock,
  D3DVolumeTexture_GetVolumeLevel, SetTexture_Inline (the game has inlined copies; Katamari's was in game code),
  SetSurfaceClip, SetSurfaceInfo, SetShaderGPRAllocation, CleanupGprAllocationSetup, SetScreenExtentQueryMode and
  ResetAllState. All of them are Katamari's native state / resource hooks. Under sa2-nx's design, which FC4's layout
  follows, the game's own functions run (`state.cpp` is not built, and only D3DResource_Destroy is hooked among the
  resources).
- **Low confidence:** the two 6-instruction UnlockRect thunks 83F1D4C8 / 83F1D4E0 (it is unclear which is which),
  LineTexture_LockRect 83F1EE60, GetCubeMapSurface 83F1EE80 (it could be GetVolumeLevel), SetTextureHeader 83F1E830
  (the sizes disagree), DrawIndexedTessellatedVertices 83F2A4B0, End/RunCommandBuffer 83F2AD50 / 83F2B170.
- **Unhooked in the tree as well:** DrawIndexedVerticesUP, BeginExport / EndExport, GetDisplayMode, D3D_IsFusion,
  D3DVertexShader_Bind, the getters, SetClipPlane, SetVertexFetchConstant, the I constants and InvalidateConstants.
  Found anyway: D3DResource_GetDevice 83F1BDD0, D3DDevice_BlockOnFence 83F2DB20, BeginTiling / EndTiling
  83F27938 / 83F27ED8, SetCommandBufferPredication 83F29170, BeginCommandBuffer 83F29B28, AllocateInlineData
  83F2DC68, XGRegisterPixelShader 83F23DA8. EndIndexedVertices: FC4's only inline end is 83F28390
  (`Ring = VerticesRingEnd`, no kick).

## Device layout: FC4 against SA2's 0x6080

FC4 allocates 0x6080 bytes, aligned 0x80, as SA2 does. `offsets_check.py` takes every device-private literal
(>= 10944) on the lines where sa2-nx moved to SA2's layout: `d3d.h`, `d3d_native.h`, and lines marked `sa2-nx` or
carrying N&B's value in brackets. It looks for the same displacement or `addi` immediate in FC4's Direct3D.

- 56 literals. **49 appear in FC4's code at the same value.** Where the line names an SA2 function, the paired FC4
  function was checked too: 0 failures.
- 4 of the other 7 are not offsets (comment ranges 0x3094 / 0x3400, the mask 0x3FFF, the build number 21119).
- **Differences between FC4 and SA2: none found.** Fields confirmed by FC4 functions that use them include: Flags
  11068-11071, the fences 11024 / 11028 / 11036 / 11056, 11008 / 11016 / 11020, predication 11060 / 11064 /
  13084-13092, VertexDeclaration 12240, IndexBuffer 12812, RenderTargets 12816, DepthStencil 12832, streams 12836 /
  12904, textures 12920, scissor 13052, pixel / vertex shader 13068 / 13072, tiling 13104-13124 / 13368 / 13556,
  VerticesRingEnd 13844, CommandBuffer 13920, InKickOff 13600, auto surfaces 15228 / 15232 / 15236, -1 words
  15340 / 21968 / 21972, PresentFenceTag 15344, critical sections 15348 / 15376, gamma 15408, SwapCount 16968,
  side buffer 17136, perf frequency 21996 / 22000, PresentationInterval 14000, BehaviorFlags 24392.
- **The other 3 are N&B values sa2-nx left in place** (not SA2's layout, so they are not FC4 differences). They must
  be moved if those paths run on FC4:
  - `D3DDevice_GetDisplayMode_hook` (device.cpp, unhooked) reads 0x34E8 / 0x34EC / 0x5434 / 0x34F0. By SA2's +404
    / +408 zones these are 13948 / 13952 / 21964 / 13956. FC4 reads 13948 and 13952 (83F394D8) and 21964 (83F190E0).
  - `SetFence` (device.cpp, the immediate-fence path) reads **0x541C (N&B 21532)**. In SA2 / FC4 that is
    **21940** (+408): FC4's Swap and fence functions read 21940 (83F19E78, 83F2D590, 83F2DEC0, 83F2E3A0,
    83F2E8F0), and sa2-nx's 21968 / 21972 are N&B's 21560 / 21564 + 408. It also reads **0x3A48 (N&B 14920)**,
    probably **15324** (+404, as 14936 -> 15340 and 14944 -> 15348). That one is unverified.

So moving Renut to FC4 means taking sa2-nx's `d3d.h`, `d3d_native.h` and device constants as they are. The
katamari-nx tree's values (2.0.5632's layout) are all wrong for FC4.

## Next (not done here)

- Retarget Renut: take sa2-nx's hook blocks (device / draw / shader / resource) and its offsets, with the FC4
  addresses above. The remap tools of the base (`renut_hook_remap_katamari.py`, `renut_device_offsets_katamari.py`)
  were written for N&B -> Katamari and do not apply.
- Check the medium rows by running: the first boot with Renut hits CreateDevice, the ring, Swap and the draws at once.
