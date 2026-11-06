# The Legend of Zelda: Ocarina of Time (`0400486024DEC000`)

Switch 2, update v131072 over base v65536. Nintendo EPD's engine (`sead` / `agl` / `gsys`, Phive, Havok and CRIWARE), SDK components at 22.2.8, on NVN2. Modules `main`, `subsdk0` (NintendoSDK_movie) and `sdk`. **The Mac host renders the AV1 opening and reaches gameplay in Link's house on an M2 Max. Movie synchronization and gameplay performance remain open; this is not a complete playthrough validation.**

The ordered rebuild and validation checklist is in [`PLAN.md`](PLAN.md). The NUP and every extracted or compiled game artifact stay in the private external work folder.

The [2026-11-06 PR audit](PR-AUDIT.md) records all 54 open Ocarina-related PRs reviewed against this checkout, the missing fixes integrated locally and the experiments deferred.

## What it needs

| Setting | Where | Why |
|---|---|---|
| `pad_layout full` | [`game.tsv`](game.tsv) | a 3D game with camera control on the right stick |
| `render_cond on` | [`game.tsv`](game.tsv) | OOT's agl passes use conditional rendering; PR [#1299](https://github.com/seedds/nxnative/pull/1299) found that running the main opaque pass unconditionally left its `EQUAL` depth test failing across the scene |
| `mem_used 0x6800000` | `game.tsv` | the rewritten `main`, `subsdk0` and `sdk` need 104 MB, above the 64 MB default |
| Provisional `mem_reserve 0x650000000`, `mem_alias 0x400000000`, `mem_stack 0x10000000`, `app_pool 0x240000000` | `game.tsv` | the NPDM declares 48 MB of system resource, so virtual address memory is on, and `main` imports `SetMemoryHeapSize`; the first heap and address-region checks must replace this starting layout with measurements |

The selected modules are 64-bit ARM. Their registered build IDs are `main` `e0f3ccfa…`, `subsdk0` `b0110087…` and `sdk` `1643a838…`.

## Files

- One private NUP container of 24 GB: a base record at v65536 and update v131072, no DLC. The update has its own ExeFS and a whole RomFS of 26,236,422,768 bytes and 186,583 files. The NUP carries a name record but no NACP or icon, so the app takes the profile's name and has no source icon.
- RomFS: 102,185 `.zs` files (16.46 GB), 46,324 `.extm` files (5.71 GB), 26,378 `.bwav` files (2.03 GB) and 26 WebM movies (1.64 GB). The largest file is the 404 MB staff-credit movie.
- The largest trees are `TerrainArc`, `PreComputedCulling`, `Tex`, `Sound`, `Bake`, `Phive`, `Voice`, `Pack` and `Model`. `Pack/ZsDic.pack.zs` is the profile's marker and holds the zstd dictionaries.

## Static survey

- `main`: 63,201,744-byte text, build `e0f3ccfaf50065ae4ea01eb5aeb13b1a`, 1,183 imports. The instruction census found 50,390 uses of `x18` and 1,264 reads of `tpidr_el0`.
- `subsdk0`: build `b0110087a7b339ef74588d3bd0b4dd5d`; the census found 3,369 uses of `x18`.
- `sdk`: build `1643a838814f9c10c696f930ed681e7f`; the census found 25,435 uses of `x18`, 441 reads of `tpidrro_el0`, 57 SVC stubs, 45 counter reads and five thread-pointer reads/writes.
- The SDK components name NVN, G3d2, UI, FreeType, HarfBuzz, NPLN, libcurl and the movie library at 22.2.8. The code names `sead`, `agl`, `gsys`, Havok and CRIWARE.

## Rewrite

- All three selected modules rewrite successfully. The rewriter accounts exactly for every instruction-census site: `main`'s 50,390 `x18` uses, `subsdk0`'s 3,369 and `sdk`'s 25,435, plus the thread-pointer, timer and SVC sites above.
- The SDK-wide function matcher found the SDK 22.2.8 `AddressRegionManager` constructor and cut its node area from 1 GB to 62 MB at `sdk+0x16ba48` and `sdk+0x16bad4`. Its observation gates for address regions and `StandardAllocator` also matched.
- The matcher for SDK 20-style 2 MB alignment of address regions found no implementation in this SDK. Nothing was patched for it; the address-region check will show whether this version needs a new general implementation.
- The rewritten modules require `mem_used 0x6800000` (104 MB).

## Shaders

- Current full Mac shader build: **42,850 of 42,850 ready, zero failures**, chain `2f70e3ea7b3f`, inputs `0408ae982de5`. It restored 38,147 shader entries and revalidated/retranslated 4,703 after map reindexing; the Metal compile cache reused 35,618 libraries and compiled zero new ones. The step took 10:45. The full library and generated tables are stamped; 650 shaders remain not proven bounded for constant-buffer optimization, rather than missing or untranslated. This Mac uses the explicitly allowed Metal compiler that differs from the lock.
- Resolved the last translation failure: `68bbe98b3bfd9876` and three other scan matches were BAHS metadata, not declared shaders. The [discovery correction](../../../docs/reference/shaders.md#bahs-metadata-mistaken-for-a-shader-record) preserves all declared program variations and all 2,765 observed boot keys.
- Libraries persist in `<build>/shader.noindex/cache/b-2f70e3ea7b3f.img`, the compile cache in `<build>/shader.noindex/cache/cas.db`, and pipeline archives in `<build>/run/pso_archive`. Keep the build folder to reuse them. The shader folder was renamed from `shader/` without discarding its contents.
- The user's unchanged 2026-11-06 12:30 installer run reused all 42,850 shaders in 11 seconds, reused the host and finished pipeline prebuild in four seconds. Use the generated `run.command` for ordinary launches; no installer run is needed. New live pipeline variants may still compile once on first use.
- The named archives are `Shader/*.Nin_Ounce_NVN2.bfsha.zs`, `Shader/ApplicationPackage.Nin_Ounce_NVN2.release.sarc.zs` and `Layout2Shader/MergeShader.Product.100.Nin_Ounce_NVN2.bfsha.zs`. They are BNSH inputs with Ampere code, compressed through the RomFS's zstd dictionaries.
- The current v131072 split produces 42,850 shader stages: 4,125 compute, 500 mesh, 22,355 pixel, 20 task and 15,850 vertex. Their ordinary BNSH source groups are joined by 22 compute stages from `Movie/Ndve/Ndve-Nvn2-vid_seq5.dat.zs`.
- The checked-in discovery tables contain all 42,850 stages, 4,125 compute-shader facts, 26,894 variation pairs and 6,296 candidate pipeline pairs. The split binary package in the private work folder is an intermediate input, not a compiled Metal library.
- Previously resolved shader-split failure on v131072, before the BAHS correction below, after the bounded NDVE reader changed source labels: regenerated `shader_map.tsv` from the current split. All 42,851 package/stage/key identities are preserved; only the 22 movie shaders' source labels and record ordering changed. The shader facts and both pair tables match exactly. See [the split-table check](../../../docs/reference/packing.md#the-split-shader-tables-differ-from-a-game-profiles).
- [`shader_seen.tsv`](shader_seen.tsv) records boot coverage only. Eleven program keys first dumped at run time are compute shaders in the movie's `NDVE` container, whose embedded `NDSR` block holds 22 NVN2 shaders. `shader_split.py` now parses that format, and all eleven keys resolve through the regenerated map.
- An earlier selected Mac build produced 16,885 Metal libraries in the current chain directory. Its selected pass reported 3,493 successful shaders (3,471 cache hits and 22 rebuilt), 697 generated variants and 134 compiled variants, with no translation failure or undecoded binding slot. It is deliberately not stamped as a full 42,343-stage build; the host therefore rejects `c1_full.tsv` and `cb_extent.tsv` until a full `dmsh_build.py` run completes.

## Open

- Expand shader coverage observations and validate the complete shader library through gameplay.
- Make a reproducible title/gameplay route from the player's first gameplay save.
- Measure the heap request and address regions, then replace the provisional memory layout.
- Validate services, input, audio, movies, saves, rendering, shader coverage and performance through gameplay.

## First Mac boot

- **Current performance investigation, 2026-11-06:** diagnostic runs from copies of the player's gameplay save reach Link's house. Console mode measures roughly 22–24 fps, with GPU frame medians around 41–44 ms even on frames with no pipeline compilation. The process footprint is about 13 GB on this 96 GB M2 Max. Initial 20-second samples compare console, handheld, MetalFX, draw-pass ordering and the encoding thread; physical controller input changes the camera between captures, so these are exploratory measurements, not a reproducible speedup claim. Reports and images remain beside the private build in `bench/save-perf-20261106/` and `bench/save-perf-profile-20261106/`. MetalFX produced no observed scaler dispatch and no improvement. Handheld measured about 26–27 fps but one run logged a Metal command-queue GPU hang during scene loading; it is not selected as the default. One profiled gameplay frame has 164 render passes, about 20.4 ms summed render work and 11.5 ms compute/copy work, spanning 43.7 ms; encoder sums exclude gaps and are not interchangeable with whole-frame time. An encoding-thread sample measured 24.9 fps versus 22.2 fps in its baseline, but their different views prevent attributing this difference to threading. A follow-up using `DM_KBD_PLAYER=own` was stopped and excluded: the extra keyboard player made the controller-selection applet loop instead of reaching gameplay. A stable route and repeated, matching-camera measurements are still needed before changing defaults.
- **Open movie synchronization:** the diagnostic logs late AV1 pictures being skipped, but also a clock reset after losing window focus while about ten seconds behind. This does not establish the player's drift with uninterrupted focus. Performance comparisons set `DM_FOCUS_KEEP=1` only for diagnostics; the player's launcher settings and save remain unchanged. See [the AV1 movie clock](../../../docs/reference/movies.md#a-game-slower-than-its-movie-plays-it-by-the-movies-clock).

- Resolved music with a black, frozen opening on the M2 Max: the submit thread was compiling NDVE pipeline `e6be82d835fbe4d3` in Apple's GPU backend, not waiting on a failed GPU fence. The offline libraries were complete, but the provisional seed contained no movie compute pipelines. The seed now prepares the 12 movie compute programs observed in the runtime list before playback. The first seeded preparation took 66.01 s; the next took 0.11 s. Captures at frames 240 and 600 show the moon/landscape and moving grass; frames 300–600 have no submit-thread pipeline builds and about 34.7 ms per frame on this setup. The 25-second diagnostic ended by its intentional watchdog, with no red fault before it. See [slow compute pipelines and startup progress](../../../docs/reference/shaders.md#slow-compute-pipelines-hidden-behind-a-black-movie). This validates the opening, not gameplay.
- Resolved Mac host build failure at the stale movie-output GPU-write marker; see [NDVE movie build integration](../../../docs/reference/rendering.md#block-corruption-after-ndve-movie-reconstruction). The host builds without compiler warnings; the movie GPU test also checks that marking its output preserves neighbouring CPU-written storage. This does not establish gameplay validation.
- The first diagnostic host build loaded all three rewritten modules, completed `nnosInitialize` / `nninitStartup`, entered `nnMain`, mounted all 187,182 packed RomFS entries and initialized an NVN 231.40 Switch 2 device on Metal. It requested a `0x18a600000`-byte heap (6.166 GiB).
- With an empty Metal cache it discovered 2,324 shader keys before the run stopped; missing libraries were expected in this discovery run and are the input to the first selected shader build.
- The first real abort was Result `0xa99` in SDK 22.2.8's `audio::detail::ListVirtualInputDevices` (`sdk+0x1f61ac`), after it tried to open the Switch 2 `auddmg:u` service. The host now answers the public virtual-input list as empty, consistent with its existing no-microphone AudioIn behavior.
- Resolved startup regression after integrating the shared input-stream implementation: both it and the original port registered `ListVirtualInputDevices`, so the loader aborted with `duplicate entry in the forced takeover list` before SDK initialization. The port now uses the single shared input-stream handler with the same empty-device result.
- The next abort came from the title's bundled gRPC initialization. It probes `nn::socket::EventFd(0, 0)` before selecting its `poll` engine; the offline host returned `ENETDOWN`, disabled that engine and then had no poll strategy. The host now provides the local event counter, read/write/close and poll semantics without enabling network sockets. The next run created the `npln-grpc` timer and executor threads normally.
- A five-second discovery run passed the service boundary, decoded the 1920x1080 AV1 opening, created the resource/scene/decompression/presentation/background workers, and reached frame 86. The watchdog stopped a live process; there was no game abort.
- The title calls `nvnCommandBufferSetComputeWorkloadPriority`, a GPU scheduling hint new to this NVN2 surface. The host has one ordered Metal queue, so it accepts the hint as an empty state operation. The initially empty provisional `pso_manifest.tsv` has been replaced by the movie compute seed described above.
- With the selected library, all eleven NDVE compute keys load. A cold pipeline archive spent about 27 seconds compiling the first four movie compute pipelines; the warm archive has no compilation stall and renders the opening at about 35 ms GPU time per frame on this Mac.
- Early captures were black because the movie itself encodes black through about timestamp 1.68 s. A decoder trace showed two one-picture pools registered at image index 0, each decoded image delivered to and read from the matching pool, and changing luma fingerprints after the encoded black lead-in. Captures at presented frames 240 and 300 show the night landscape and moon, confirming AV1 decode, NV12 upload, all NDVE compute passes and final presentation together.
- The NDVE raw-pointer stores originally overflowed the 1,024-page write log on every dispatch, leaving all GPU writes conservative. The general log now holds 8,192 exact pages: it learns the movie output's one pool over 11 dispatches with no overflow. On a warm archive this lowers the opening's GPU time from about 35 ms to 15 ms per frame (frames 300–600: p50 15.30 ms, p95 15.64 ms); presentation stays at about 16.67 ms. The chain change's first compute-pipeline build took 42.3 seconds once.
- Decoder input reaches ordinary protocol back-pressure at the 12-picture host queue during startup. The game handles the returned busy result, retries, and continues releasing and reading pictures; this is no longer reported as a red fault. The remaining red diagnostics are the intentionally unstamped partial shader library and its missing generated constant-buffer tables.

## Found on this game

- [Slow compute pipelines hidden behind a black movie](../../../docs/reference/shaders.md#slow-compute-pipelines-hidden-behind-a-black-movie): missing movie compute prewarm rows stalled playback, and a mixed-task duration estimate hid preparation progress.
- [BAHS metadata mistaken for a shader record](../../../docs/reference/shaders.md#bahs-metadata-mistaken-for-a-shader-record): the failed compute entry and three unreferenced graphics entries were data matches outside the declared binary-entry offsets.
- [Block corruption after NDVE movie reconstruction](../../../docs/reference/rendering.md#block-corruption-after-ndve-movie-reconstruction): the optional direct movie path needed the current texture-range GPU-write marker to compile.
- [No audio input devices](../../../docs/reference/audio.md#no-audio-input-devices): SDK 22's virtual-input list opened `auddmg:u` and aborted when no microphone service existed.
- [Local `eventfd` while network sockets are offline](../../../docs/reference/services.md#local-eventfd-while-network-sockets-are-offline): the bundled gRPC runtime disabled its only poll engine when the offline host rejected its local event counter.
- [Global memory at an address loaded from memory](../../../docs/reference/shaders.md#global-memory-at-an-address-loaded-from-memory): seven NDVE compute shaders write image surfaces through loaded pointers, exceeding the original 1,024-page write log on every dispatch.
