2e4f7a8: sub      sp, sp, #0xd0
2e4f7ac: stp      d9, d8, [sp, #0x70]
2e4f7b0: str      x26, [sp, #0x80]
2e4f7b4: stp      x25, x24, [sp, #0x90]
2e4f7b8: stp      x23, x22, [sp, #0xa0]
2e4f7bc: stp      x21, x20, [sp, #0xb0]
2e4f7c0: stp      x19, x30, [sp, #0xc0]
2e4f7c4: adrp     x24, #0xce92000
2e4f7c8: adrp     x23, #0xc685000
2e4f7cc: ldrb     w8, [x24, #0x24c]
2e4f7d0: ldr      x23, [x23, #0x308]
2e4f7d4: mov      x20, x3
2e4f7d8: mov      x21, x2
2e4f7dc: mov      x22, x1
2e4f7e0: mov      x19, x0
2e4f7e4: tbnz     w8, #0, #0x2e4f844
2e4f7e8: adrp     x0, #0xc6bb000
2e4f7ec: ldr      x0, [x0, #0x258]
2e4f7f0: bl       #0x237e160
2e4f7f4: adrp     x0, #0xc635000
2e4f7f8: ldr      x0, [x0, #0xac8]
2e4f7fc: bl       #0x237e160
2e4f800: adrp     x0, #0xc663000
2e4f804: ldr      x0, [x0, #0xbb0]
2e4f808: bl       #0x237e160
2e4f80c: adrp     x0, #0xc66f000
2e4f810: ldr      x0, [x0, #0x980]
2e4f814: bl       #0x237e160
2e4f818: adrp     x0, #0xc651000
2e4f81c: ldr      x0, [x0, #0xe68]
2e4f820: bl       #0x237e160
2e4f824: adrp     x0, #0xc69e000
2e4f828: ldr      x0, [x0, #0x560]
2e4f82c: bl       #0x237e160
2e4f830: adrp     x0, #0xc685000
2e4f834: ldr      x0, [x0, #0x308]
2e4f838: bl       #0x237e160
2e4f83c: mov      w8, #1
2e4f840: strb     w8, [x24, #0x24c]
2e4f844: ldr      x8, [x23]
2e4f848: str      xzr, [sp, #0x88]
2e4f84c: stp      xzr, xzr, [sp, #0x60]
2e4f850: ldr      x8, [x8, #0xb8]
2e4f854: ldr      x0, [x8, #0x60]
2e4f858: cbz      x0, #0x2e4f878
2e4f85c: mov      x1, x19
2e4f860: mov      x2, x22
2e4f864: mov      x3, x21
2e4f868: mov      x4, x20
2e4f86c: mov      x5, xzr
2e4f870: bl       #0x4e5a36c ; -> XLua.DelegateBridge.__Gen_Delegate_Imp42
2e4f874: b        #0x2e4fc50
2e4f878: mov      x0, x19
2e4f87c: mov      x1, x22
2e4f880: mov      x2, x21
2e4f884: mov      x3, x20
2e4f888: mov      x4, xzr
2e4f88c: bl       #0x2559c3c ; -> Torappu.Battle.AbilityStandard.DoCastOnTargets
2e4f890: tbz      w0, #0, #0x2e4f89c
2e4f894: mov      w0, #1
2e4f898: b        #0x2e4fc50
2e4f89c: adrp     x21, #0xc677000
2e4f8a0: ldr      x21, [x21, #0x6d0]
2e4f8a4: ldrb     w8, [x21]
2e4f8a8: cbz      w8, #0x2e4f8b4
2e4f8ac: ldr      x0, [x19]
2e4f8b0: bl       #0x23c9be0
2e4f8b4: ldr      x8, [x19]
2e4f8b8: mov      x0, x19
2e4f8bc: ldr      x9, [x8, #0x260]
2e4f8c0: ldr      x1, [x8, #0x268]
2e4f8c4: blr      x9
2e4f8c8: tbz      w0, #0, #0x2e4fc4c
2e4f8cc: adrp     x22, #0xc6bb000
2e4f8d0: adrp     x24, #0xc651000
2e4f8d4: adrp     x23, #0xc66f000
2e4f8d8: adrp     x25, #0xc69e000
2e4f8dc: ldrb     w8, [x19, #0x241]
2e4f8e0: ldr      x22, [x22, #0x258]
2e4f8e4: ldr      x24, [x24, #0xe68]
2e4f8e8: ldr      x23, [x23, #0x980]
2e4f8ec: ldr      x25, [x25, #0x560]
2e4f8f0: cbz      w8, #0x2e4f9f4
2e4f8f4: adrp     x8, #0xc635000
2e4f8f8: ldr      x8, [x8, #0xac8]
2e4f8fc: ldp      s9, s8, [x19, #0xe0]
2e4f900: ldr      x0, [x8]
2e4f904: ldr      w8, [x0, #0xe0]
2e4f908: cbnz     w8, #0x2e4f910
2e4f90c: bl       #0x237e260
2e4f910: mov      v0.16b, v9.16b
2e4f914: mov      v1.16b, v8.16b
2e4f918: mov      x0, xzr
2e4f91c: bl       #0x40093dc ; -> Torappu.GridPosition.FromVectorPosition
2e4f920: str      x0, [sp, #0x68]
2e4f924: ldr      x20, [x19, #0x258]
2e4f928: add      x0, sp, #0x68
2e4f92c: mov      x1, xzr
2e4f930: bl       #0x40091b0 ; -> Torappu.GridPosition.get_asLocalPosition
2e4f934: movi     v2.2d, #0000000000000000
2e4f938: add      x0, sp, #0x30
2e4f93c: mov      x1, xzr
2e4f940: str      xzr, [sp, #0x50]
2e4f944: stp      q2, q2, [sp, #0x30]
2e4f948: bl       #0x268695c ; -> Torappu.Battle.FixedPosition..ctor
2e4f94c: ldp      q0, q1, [sp, #0x30]
2e4f950: ldr      x8, [sp, #0x50]
2e4f954: ldr      x0, [x22]
2e4f958: mov      x1, sp
2e4f95c: stp      q0, q1, [sp]
2e4f960: str      x8, [sp, #0x20]
2e4f964: bl       #0x237e268
2e4f968: ldrb     w8, [x21]
2e4f96c: mov      x21, x0
2e4f970: cbz      w8, #0x2e4f97c
2e4f974: ldr      x0, [x19]
2e4f978: bl       #0x23c9be0
2e4f97c: ldr      x8, [x19]
2e4f980: add      x2, sp, #0x88
2e4f984: mov      x0, x19
2e4f988: mov      x1, x21
2e4f98c: ldr      x9, [x8, #0x890]
2e4f990: ldr      x3, [x8, #0x898]
2e4f994: blr      x9
2e4f998: ldr      x1, [x24]
2e4f99c: bl       #0x7af658c
2e4f9a0: cbz      x20, #0x2e4fc74
2e4f9a4: ldr      w9, [x20, #0x1c]
2e4f9a8: ldr      x8, [x20, #0x10]
2e4f9ac: ldr      x26, [x23]
2e4f9b0: add      w9, w9, #1
2e4f9b4: str      w9, [x20, #0x1c]
2e4f9b8: cbz      x8, #0x2e4fc74
2e4f9bc: ldrsw    x9, [x20, #0x18]
2e4f9c0: ldr      w10, [x8, #0x18]
2e4f9c4: mov      x22, x0
2e4f9c8: mov      x21, x1
2e4f9cc: cmp      w9, w10
2e4f9d0: b.hs     #0x2e4fae4
2e4f9d4: add      w10, w9, #1
2e4f9d8: add      x0, x8, x9, lsl #4
2e4f9dc: str      w10, [x20, #0x18]
2e4f9e0: str      x22, [x0, #0x20]!
2e4f9e4: mov      x1, xzr
2e4f9e8: str      x21, [x0, #8]
2e4f9ec: bl       #0x237e114
2e4f9f0: b        #0x2e4fb1c
2e4f9f4: ldrb     w8, [x21]
2e4f9f8: cbz      w8, #0x2e4fa04
2e4f9fc: ldr      x0, [x19]
2e4fa00: bl       #0x23c9be0
2e4fa04: ldr      x8, [x19]
2e4fa08: mov      x0, x19
2e4fa0c: ldr      x9, [x8, #0x880]
2e4fa10: ldr      x1, [x8, #0x888]
2e4fa14: blr      x9
2e4fa18: tbz      w0, #0, #0x2e4fc4c
2e4fa1c: ldp      s0, s1, [x19, #0xe0]
2e4fa20: ldr      x20, [x19, #0x258]
2e4fa24: movi     v2.2d, #0000000000000000
2e4fa28: add      x0, sp, #0x30
2e4fa2c: mov      x1, xzr
2e4fa30: str      xzr, [sp, #0x50]
2e4fa34: stp      q2, q2, [sp, #0x30]
2e4fa38: bl       #0x268695c ; -> Torappu.Battle.FixedPosition..ctor
2e4fa3c: ldp      q0, q1, [sp, #0x30]
2e4fa40: ldr      x8, [sp, #0x50]
2e4fa44: ldr      x0, [x22]
2e4fa48: mov      x1, sp
2e4fa4c: stp      q0, q1, [sp]
2e4fa50: str      x8, [sp, #0x20]
2e4fa54: bl       #0x237e268
2e4fa58: ldrb     w8, [x21]
2e4fa5c: mov      x21, x0
2e4fa60: cbz      w8, #0x2e4fa6c
2e4fa64: ldr      x0, [x19]
2e4fa68: bl       #0x23c9be0
2e4fa6c: ldr      x8, [x19]
2e4fa70: add      x2, sp, #0x60
2e4fa74: mov      x0, x19
2e4fa78: mov      x1, x21
2e4fa7c: ldr      x9, [x8, #0x890]
2e4fa80: ldr      x3, [x8, #0x898]
2e4fa84: blr      x9
2e4fa88: ldr      x1, [x24]
2e4fa8c: bl       #0x7af658c
2e4fa90: cbz      x20, #0x2e4fc74
2e4fa94: ldr      w9, [x20, #0x1c]
2e4fa98: ldr      x8, [x20, #0x10]
2e4fa9c: ldr      x26, [x23]
2e4faa0: add      w9, w9, #1
2e4faa4: str      w9, [x20, #0x1c]
2e4faa8: cbz      x8, #0x2e4fc74
2e4faac: ldrsw    x9, [x20, #0x18]
2e4fab0: ldr      w10, [x8, #0x18]
2e4fab4: mov      x22, x0
2e4fab8: mov      x21, x1
2e4fabc: cmp      w9, w10
2e4fac0: b.hs     #0x2e4fb50
2e4fac4: add      w10, w9, #1
2e4fac8: add      x0, x8, x9, lsl #4
2e4facc: str      w10, [x20, #0x18]
2e4fad0: str      x22, [x0, #0x20]!
2e4fad4: mov      x1, xzr
2e4fad8: str      x21, [x0, #8]
2e4fadc: bl       #0x237e114
2e4fae0: b        #0x2e4fb88
2e4fae4: ldr      x8, [x26, #0x20]
2e4fae8: ldr      x8, [x8, #0xc0]
2e4faec: ldr      x3, [x8, #0x58]
2e4faf0: ldr      x8, [x3, #0x20]
2e4faf4: cbnz     x8, #0x2e4fb0c
2e4faf8: ldr      x8, [x3]
2e4fafc: blr      x8
2e4fb00: ldr      x8, [x26, #0x20]
2e4fb04: ldr      x8, [x8, #0xc0]
2e4fb08: ldr      x3, [x8, #0x58]
2e4fb0c: mov      x0, x20
2e4fb10: mov      x1, x22
2e4fb14: mov      x2, x21
2e4fb18: bl       #0x6f2eff4
2e4fb1c: ldr      x0, [x25]
2e4fb20: ldr      x20, [sp, #0x88]
2e4fb24: ldr      w8, [x0, #0xe0]
2e4fb28: cbnz     w8, #0x2e4fb30
2e4fb2c: bl       #0x237e260
2e4fb30: mov      x0, x20
2e4fb34: mov      x1, xzr
2e4fb38: mov      x2, xzr
2e4fb3c: bl       #0x97a04d8 ; -> UnityEngine.Object.op_Inequality
2e4fb40: tbz      w0, #0, #0x2e4fc4c
2e4fb44: ldr      x19, [x19, #0x258]
2e4fb48: ldr      x0, [sp, #0x88]
2e4fb4c: b        #0x2e4fbb8
2e4fb50: ldr      x8, [x26, #0x20]
2e4fb54: ldr      x8, [x8, #0xc0]
2e4fb58: ldr      x3, [x8, #0x58]
2e4fb5c: ldr      x8, [x3, #0x20]
2e4fb60: cbnz     x8, #0x2e4fb78
2e4fb64: ldr      x8, [x3]
2e4fb68: blr      x8
2e4fb6c: ldr      x8, [x26, #0x20]
2e4fb70: ldr      x8, [x8, #0xc0]
2e4fb74: ldr      x3, [x8, #0x58]
2e4fb78: mov      x0, x20
2e4fb7c: mov      x1, x22
2e4fb80: mov      x2, x21
2e4fb84: bl       #0x6f2eff4
2e4fb88: ldr      x0, [x25]
2e4fb8c: ldr      x20, [sp, #0x60]
2e4fb90: ldr      w8, [x0, #0xe0]
2e4fb94: cbnz     w8, #0x2e4fb9c
2e4fb98: bl       #0x237e260
2e4fb9c: mov      x0, x20
2e4fba0: mov      x1, xzr
2e4fba4: mov      x2, xzr
2e4fba8: bl       #0x97a04d8 ; -> UnityEngine.Object.op_Inequality
2e4fbac: tbz      w0, #0, #0x2e4fc4c
2e4fbb0: ldr      x19, [x19, #0x258]
2e4fbb4: ldr      x0, [sp, #0x60]
2e4fbb8: ldr      x1, [x24]
2e4fbbc: bl       #0x7af658c
2e4fbc0: cbz      x19, #0x2e4fc74
2e4fbc4: ldr      w9, [x19, #0x1c]
2e4fbc8: ldr      x8, [x19, #0x10]
2e4fbcc: ldr      x22, [x23]
2e4fbd0: add      w9, w9, #1
2e4fbd4: str      w9, [x19, #0x1c]
2e4fbd8: cbz      x8, #0x2e4fc74
2e4fbdc: ldrsw    x9, [x19, #0x18]
2e4fbe0: ldr      w10, [x8, #0x18]
2e4fbe4: mov      x21, x0
2e4fbe8: mov      x20, x1
2e4fbec: cmp      w9, w10
2e4fbf0: b.hs     #0x2e4fc14
2e4fbf4: add      w10, w9, #1
2e4fbf8: add      x0, x8, x9, lsl #4
2e4fbfc: str      w10, [x19, #0x18]
2e4fc00: str      x21, [x0, #0x20]!
2e4fc04: mov      x1, xzr
2e4fc08: str      x20, [x0, #8]
2e4fc0c: bl       #0x237e114
2e4fc10: b        #0x2e4fc4c
2e4fc14: ldr      x8, [x22, #0x20]
2e4fc18: ldr      x8, [x8, #0xc0]
2e4fc1c: ldr      x3, [x8, #0x58]
2e4fc20: ldr      x8, [x3, #0x20]
2e4fc24: cbnz     x8, #0x2e4fc3c
2e4fc28: ldr      x8, [x3]
2e4fc2c: blr      x8
2e4fc30: ldr      x8, [x22, #0x20]
2e4fc34: ldr      x8, [x8, #0xc0]
2e4fc38: ldr      x3, [x8, #0x58]
2e4fc3c: mov      x0, x19
2e4fc40: mov      x1, x21
2e4fc44: mov      x2, x20
2e4fc48: bl       #0x6f2eff4
2e4fc4c: mov      w0, wzr
2e4fc50: ldp      x19, x30, [sp, #0xc0]
2e4fc54: ldp      x21, x20, [sp, #0xb0]
2e4fc58: ldp      x23, x22, [sp, #0xa0]
2e4fc5c: ldp      x25, x24, [sp, #0x90]
2e4fc60: ldr      x26, [sp, #0x80]
2e4fc64: ldp      d9, d8, [sp, #0x70]
2e4fc68: and      w0, w0, #1
2e4fc6c: add      sp, sp, #0xd0
2e4fc70: ret      
2e4fc74: bl       #0x237e284