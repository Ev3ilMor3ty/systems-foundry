# Physical test coverage

| D model | Latest original set | Previous set | Shared profile software | Real iPhone/iPad | BLE / flash / recovery | Field weakening / braking |
| --- | --- | --- | --- | --- | --- | --- |
| MAX G3 D | Unknown | Unknown | Covered by core suite | Not tested | Not implemented/tested | Not tested |
| F3 Pro D | Unknown | Unknown | Covered by core suite | Not tested | Not implemented/tested | Not tested |
| ZT3 Pro D | Unknown | Unknown | Covered by core suite | Not tested | Not implemented/tested | Not tested |
| E3 Pro D | Unknown | Unknown | Covered by core suite | Not tested | Not implemented/tested | Not tested |

Shared software coverage is not hardware support. Each physical result requires exact region, motor, controller, battery and board revision; exact VCU/MCU/BLE/BMS identities; authenticity evidence; tested transfer/recovery; current and thermal measurements; braking checks; immutable logs including failures. Different revisions inherit no result. Separate unloaded motor speed from measured speed under load. No 70+ km/h result exists.

Statistics checks cover correct DC-versus-phase arithmetic, simultaneous-sample peaks, charging/regen signs, unknown/zero values, nominal-versus-nameplate energy, schema migration, per-model persistence and the bounded manual history. They do not measure a physical motor or validate any current limit.
