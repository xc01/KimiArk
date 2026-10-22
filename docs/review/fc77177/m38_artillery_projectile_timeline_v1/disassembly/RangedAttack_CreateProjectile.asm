2e52bd8: str      x24, [sp, #-0x40]!
2e52bdc: stp      x23, x22, [sp, #0x10]
2e52be0: stp      x21, x20, [sp, #0x20]
2e52be4: stp      x19, x30, [sp, #0x30]
2e52be8: adrp     x22, #0xce92000
2e52bec: adrp     x23, #0xc685000
2e52bf0: ldrb     w8, [x22, #0x258]
2e52bf4: ldr      x23, [x23, #0x308]
2e52bf8: mov      x20, x2
2e52bfc: mov      x21, x1
2e52c00: mov      x19, x0
2e52c04: tbnz     w8, #0, #0x2e52c34
2e52c08: adrp     x0, #0xc6a9000
2e52c0c: ldr      x0, [x0, #0x98]
2e52c10: bl       #0x237e160
2e52c14: adrp     x0, #0xc685000
2e52c18: ldr      x0, [x0, #0x308]
2e52c1c: bl       #0x237e160
2e52c20: adrp     x0, #0xc6ac000
2e52c24: ldr      x0, [x0, #0x750]
2e52c28: bl       #0x237e160
2e52c2c: mov      w8, #1
2e52c30: strb     w8, [x22, #0x258]
2e52c34: ldr      x8, [x23]
2e52c38: ldr      x8, [x8, #0xb8]
2e52c3c: ldr      x0, [x8, #0xc0]
2e52c40: cbz      x0, #0x2e52c68
2e52c44: mov      x1, x19
2e52c48: mov      x2, x21
2e52c4c: mov      x3, x20
2e52c50: ldp      x19, x30, [sp, #0x30]
2e52c54: ldp      x21, x20, [sp, #0x20]
2e52c58: ldp      x23, x22, [sp, #0x10]
2e52c5c: mov      x4, xzr
2e52c60: ldr      x24, [sp], #0x40
2e52c64: b        #0x50b3058 ; -> XLua.DelegateBridge.__Gen_Delegate_Imp4409
2e52c68: adrp     x8, #0xc6ac000
2e52c6c: ldr      x8, [x8, #0x750]
2e52c70: ldr      x0, [x8]
2e52c74: bl       #0x7f14c0c
2e52c78: adrp     x8, #0xc677000
2e52c7c: ldr      x8, [x8, #0x6d0]
2e52c80: mov      x22, x0
2e52c84: ldrb     w8, [x8]
2e52c88: cbz      w8, #0x2e52c94
2e52c8c: ldr      x0, [x19]
2e52c90: bl       #0x23c9be0
2e52c94: ldr      x8, [x19]
2e52c98: mov      x0, x19
2e52c9c: ldr      x9, [x8, #0x8a0]
2e52ca0: ldr      x1, [x8, #0x8a8]
2e52ca4: blr      x9
2e52ca8: mov      x23, x0
2e52cac: mov      x0, x19
2e52cb0: mov      x1, xzr
2e52cb4: bl       #0x254f33c ; -> Torappu.Battle.Ability.get_owner
2e52cb8: mov      x24, x0
2e52cbc: mov      x0, x19
2e52cc0: bl       #0x2e5730c ; -> Torappu.Battle.Abilities.RangedAttack._GetMountPoint
2e52cc4: cbz      x22, #0x2e52d44
2e52cc8: mov      x3, x0
2e52ccc: mov      x0, x22
2e52cd0: mov      x1, x23
2e52cd4: mov      x2, x24
2e52cd8: mov      x4, x21
2e52cdc: mov      x5, x19
2e52ce0: mov      x6, x20
2e52ce4: mov      x7, xzr
2e52ce8: bl       #0x25a989c ; -> Torappu.Battle.BattleController.CreateProjectile
2e52cec: ldrb     w8, [x19, #0x250]
2e52cf0: mov      x20, x0
2e52cf4: cbz      w8, #0x2e52d2c
2e52cf8: mov      x0, x19
2e52cfc: mov      x1, xzr
2e52d00: bl       #0x254f33c ; -> Torappu.Battle.Ability.get_owner
2e52d04: cbz      x0, #0x2e52d44
2e52d08: mov      x1, xzr
2e52d0c: bl       #0x2669f58 ; -> Torappu.Battle.Entity.get_eventPool
2e52d10: cbz      x0, #0x2e52d44
2e52d14: adrp     x8, #0xc6a9000
2e52d18: ldr      x8, [x8, #0x98]
2e52d1c: mov      w1, #0x28
2e52d20: mov      x2, x20
2e52d24: ldr      x3, [x8]
2e52d28: bl       #0x69f8250
2e52d2c: mov      x0, x20
2e52d30: ldp      x19, x30, [sp, #0x30]
2e52d34: ldp      x21, x20, [sp, #0x20]
2e52d38: ldp      x23, x22, [sp, #0x10]
2e52d3c: ldr      x24, [sp], #0x40
2e52d40: ret      
2e52d44: bl       #0x237e284