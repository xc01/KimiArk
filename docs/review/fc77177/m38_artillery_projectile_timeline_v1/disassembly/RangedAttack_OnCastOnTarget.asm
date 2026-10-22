2e4ee9c: sub      sp, sp, #0xb0
2e4eea0: stp      d9, d8, [sp, #0x60]
2e4eea4: stp      x25, x24, [sp, #0x70]
2e4eea8: stp      x23, x22, [sp, #0x80]
2e4eeac: stp      x21, x20, [sp, #0x90]
2e4eeb0: stp      x19, x30, [sp, #0xa0]
2e4eeb4: adrp     x25, #0xce92000
2e4eeb8: adrp     x24, #0xc685000
2e4eebc: ldrb     w8, [x25, #0x24d]
2e4eec0: ldr      x24, [x24, #0x308]
2e4eec4: mov      x22, x4
2e4eec8: mov      x23, x3
2e4eecc: mov      x21, x2
2e4eed0: mov      x20, x1
2e4eed4: mov      x19, x0
2e4eed8: tbnz     w8, #0, #0x2e4ef2c
2e4eedc: adrp     x0, #0xc6bb000
2e4eee0: ldr      x0, [x0, #0x258]
2e4eee4: bl       #0x237e160
2e4eee8: adrp     x0, #0xc663000
2e4eeec: ldr      x0, [x0, #0xbb0]
2e4eef0: bl       #0x237e160
2e4eef4: adrp     x0, #0xc66f000
2e4eef8: ldr      x0, [x0, #0x980]
2e4eefc: bl       #0x237e160
2e4ef00: adrp     x0, #0xc651000
2e4ef04: ldr      x0, [x0, #0xe68]
2e4ef08: bl       #0x237e160
2e4ef0c: adrp     x0, #0xc69e000
2e4ef10: ldr      x0, [x0, #0x560]
2e4ef14: bl       #0x237e160
2e4ef18: adrp     x0, #0xc685000
2e4ef1c: ldr      x0, [x0, #0x308]
2e4ef20: bl       #0x237e160
2e4ef24: mov      w8, #1
2e4ef28: strb     w8, [x25, #0x24d]
2e4ef2c: ldr      x8, [x24]
2e4ef30: str      xzr, [sp, #0x58]
2e4ef34: ldr      x8, [x8, #0xb8]
2e4ef38: ldr      x0, [x8, #0x68]
2e4ef3c: cbz      x0, #0x2e4ef60
2e4ef40: mov      x1, x19
2e4ef44: mov      x2, x20
2e4ef48: mov      x3, x21
2e4ef4c: mov      x4, x23
2e4ef50: mov      x5, x22
2e4ef54: mov      x6, xzr
2e4ef58: bl       #0x4e8ca58 ; -> XLua.DelegateBridge.__Gen_Delegate_Imp442
2e4ef5c: b        #0x2e4f3c0
2e4ef60: adrp     x24, #0xc651000
2e4ef64: adrp     x23, #0xc66f000
2e4ef68: ldr      x24, [x24, #0xe68]
2e4ef6c: ldr      x23, [x23, #0x980]
2e4ef70: mov      x0, x19
2e4ef74: mov      x1, x20
2e4ef78: mov      x2, x21
2e4ef7c: mov      x3, xzr
2e4ef80: mov      x4, xzr
2e4ef84: mov      x5, xzr
2e4ef88: bl       #0x2557d20 ; -> Torappu.Battle.AbilityStandard.OnCastOnTarget
2e4ef8c: ldr      w8, [x19, #0x238]
2e4ef90: sub      w8, w8, #1
2e4ef94: cmp      w8, #3
2e4ef98: b.hi     #0x2e4f214
2e4ef9c: adrp     x9, #0x99e4000
2e4efa0: add      x9, x9, #0x5b
2e4efa4: adrp     x22, #0xc6bb000
2e4efa8: adr      x10, #0x2e4efbc
2e4efac: ldrb     w11, [x9, x8]
2e4efb0: add      x10, x10, x11, lsl #2
2e4efb4: ldr      x22, [x22, #0x258]
2e4efb8: br       x10
2e4efbc: ldp      s0, s1, [x19, #0xe0]
2e4efc0: ldr      x20, [x19, #0x258]
2e4efc4: movi     v2.2d, #0000000000000000
2e4efc8: add      x0, sp, #0x30
2e4efcc: mov      x1, xzr
2e4efd0: str      xzr, [sp, #0x50]
2e4efd4: stp      q2, q2, [sp, #0x30]
2e4efd8: bl       #0x268695c ; -> Torappu.Battle.FixedPosition..ctor
2e4efdc: ldp      q0, q1, [sp, #0x30]
2e4efe0: ldr      x8, [sp, #0x50]
2e4efe4: ldr      x0, [x22]
2e4efe8: mov      x1, sp
2e4efec: stp      q0, q1, [sp]
2e4eff0: str      x8, [sp, #0x20]
2e4eff4: bl       #0x237e268
2e4eff8: adrp     x8, #0xc677000
2e4effc: ldr      x8, [x8, #0x6d0]
2e4f000: b        #0x2e65648
2e4f004: b        #0x2e4f15c
2e4f008: cbz      x20, #0x2e4f3dc
2e4f00c: ldr      x21, [x19, #0x258]
2e4f010: mov      x0, x20
2e4f014: mov      x1, xzr
2e4f018: bl       #0x2a5bfd4 ; -> Torappu.Battle.VisualObject.get_mapPositionV3
2e4f01c: movi     v3.2d, #0000000000000000
2e4f020: add      x0, sp, #0x30
2e4f024: mov      x1, xzr
2e4f028: str      xzr, [sp, #0x50]
2e4f02c: stp      q3, q3, [sp, #0x30]
2e4f030: bl       #0x2686ab0 ; -> Torappu.Battle.FixedPosition..ctor
2e4f034: ldp      q0, q1, [sp, #0x30]
2e4f038: ldr      x8, [sp, #0x50]
2e4f03c: ldr      x0, [x22]
2e4f040: mov      x1, sp
2e4f044: stp      q0, q1, [sp]
2e4f048: str      x8, [sp, #0x20]
2e4f04c: bl       #0x237e268
2e4f050: b        #0x2e4f228
2e4f054: cbz      x20, #0x2e4f3dc
2e4f058: adrp     x25, #0xc677000
2e4f05c: ldr      x25, [x25, #0x6d0]
2e4f060: ldr      x21, [x19, #0x258]
2e4f064: ldrb     w8, [x25]
2e4f068: cbz      w8, #0x2e4f074
2e4f06c: ldr      x0, [x20]
2e4f070: bl       #0x23c9be0
2e4f074: ldr      x8, [x20]
2e4f078: mov      x0, x20
2e4f07c: ldr      x9, [x8, #0x480]
2e4f080: ldr      x1, [x8, #0x488]
2e4f084: blr      x9
2e4f088: mov      x1, x0
2e4f08c: movi     v0.2d, #0000000000000000
2e4f090: add      x0, sp, #0x30
2e4f094: mov      x2, xzr
2e4f098: str      xzr, [sp, #0x50]
2e4f09c: stp      q0, q0, [sp, #0x30]
2e4f0a0: bl       #0x2686b3c ; -> Torappu.Battle.FixedPosition..ctor
2e4f0a4: ldp      q0, q1, [sp, #0x30]
2e4f0a8: ldr      x8, [sp, #0x50]
2e4f0ac: ldr      x0, [x22]
2e4f0b0: mov      x1, sp
2e4f0b4: stp      q0, q1, [sp]
2e4f0b8: str      x8, [sp, #0x20]
2e4f0bc: bl       #0x237e268
2e4f0c0: ldrb     w8, [x25]
2e4f0c4: b        #0x2e4f234
2e4f0c8: cbz      x20, #0x2e4f3dc
2e4f0cc: mov      x0, x20
2e4f0d0: mov      x1, xzr
2e4f0d4: bl       #0x2a5bfd4 ; -> Torappu.Battle.VisualObject.get_mapPositionV3
2e4f0d8: adrp     x21, #0xc677000
2e4f0dc: ldr      x21, [x21, #0x6d0]
2e4f0e0: mov      v8.16b, v0.16b
2e4f0e4: mov      v9.16b, v1.16b
2e4f0e8: ldrb     w8, [x21]
2e4f0ec: cbz      w8, #0x2e4f0f8
2e4f0f0: ldr      x0, [x20]
2e4f0f4: bl       #0x23c9be0
2e4f0f8: ldr      x8, [x20]
2e4f0fc: mov      x0, x20
2e4f100: ldr      x9, [x8, #0x480]
2e4f104: ldr      x1, [x8, #0x488]
2e4f108: blr      x9
2e4f10c: cbz      x0, #0x2e4f3dc
2e4f110: mov      x1, xzr
2e4f114: bl       #0x2a5bfd4 ; -> Torappu.Battle.VisualObject.get_mapPositionV3
2e4f118: ldr      x20, [x19, #0x258]
2e4f11c: movi     v0.2d, #0000000000000000
2e4f120: stp      q0, q0, [sp, #0x30]
2e4f124: add      x0, sp, #0x30
2e4f128: mov      v0.16b, v8.16b
2e4f12c: mov      v1.16b, v9.16b
2e4f130: mov      x1, xzr
2e4f134: str      xzr, [sp, #0x50]
2e4f138: bl       #0x2686ab0 ; -> Torappu.Battle.FixedPosition..ctor
2e4f13c: ldp      q0, q1, [sp, #0x30]
2e4f140: ldr      x8, [sp, #0x50]
2e4f144: ldr      x0, [x22]
2e4f148: mov      x1, sp
2e4f14c: stp      q0, q1, [sp]
2e4f150: str      x8, [sp, #0x20]
2e4f154: bl       #0x237e268
2e4f158: ldrb     w8, [x21]
2e4f15c: mov      x21, x0
2e4f160: cbz      w8, #0x2e4f16c
2e4f164: ldr      x0, [x19]
2e4f168: bl       #0x23c9be0
2e4f16c: ldr      x8, [x19]
2e4f170: add      x2, sp, #0x58
2e4f174: mov      x0, x19
2e4f178: mov      x1, x21
2e4f17c: ldr      x9, [x8, #0x890]
2e4f180: ldr      x3, [x8, #0x898]
2e4f184: blr      x9
2e4f188: ldr      x1, [x24]
2e4f18c: bl       #0x7af658c
2e4f190: cbz      x20, #0x2e4f3dc
2e4f194: ldr      w9, [x20, #0x1c]
2e4f198: ldr      x8, [x20, #0x10]
2e4f19c: ldr      x25, [x23]
2e4f1a0: add      w9, w9, #1
2e4f1a4: str      w9, [x20, #0x1c]
2e4f1a8: cbz      x8, #0x2e4f3dc
2e4f1ac: ldrsw    x9, [x20, #0x18]
2e4f1b0: ldr      w10, [x8, #0x18]
2e4f1b4: mov      x22, x0
2e4f1b8: mov      x21, x1
2e4f1bc: cmp      w9, w10
2e4f1c0: b.hs     #0x2e4f1dc
2e4f1c4: add      w10, w9, #1
2e4f1c8: add      x0, x8, x9, lsl #4
2e4f1cc: str      w10, [x20, #0x18]
2e4f1d0: str      x22, [x0, #0x20]!
2e4f1d4: str      x21, [x0, #8]
2e4f1d8: b        #0x2e4f2b0
2e4f1dc: ldr      x8, [x25, #0x20]
2e4f1e0: ldr      x8, [x8, #0xc0]
2e4f1e4: ldr      x3, [x8, #0x58]
2e4f1e8: ldr      x8, [x3, #0x20]
2e4f1ec: cbnz     x8, #0x2e4f204
2e4f1f0: ldr      x8, [x3]
2e4f1f4: blr      x8
2e4f1f8: ldr      x8, [x25, #0x20]
2e4f1fc: ldr      x8, [x8, #0xc0]
2e4f200: ldr      x3, [x8, #0x58]
2e4f204: mov      x0, x20
2e4f208: mov      x1, x22
2e4f20c: mov      x2, x21
2e4f210: b        #0x2e4f2f0
2e4f214: cbz      x20, #0x2e4f3dc
2e4f218: ldr      x21, [x19, #0x258]
2e4f21c: mov      x0, x20
2e4f220: mov      x1, xzr
2e4f224: bl       #0x266c9e8 ; -> Torappu.Battle.Entity.get_hitMountPoint
2e4f228: adrp     x8, #0xc677000
2e4f22c: ldr      x8, [x8, #0x6d0]
2e4f230: ldrb     w8, [x8]
2e4f234: mov      x20, x0
2e4f238: cbz      w8, #0x2e4f244
2e4f23c: ldr      x0, [x19]
2e4f240: bl       #0x23c9be0
2e4f244: ldr      x8, [x19]
2e4f248: add      x2, sp, #0x58
2e4f24c: mov      x0, x19
2e4f250: mov      x1, x20
2e4f254: ldr      x9, [x8, #0x890]
2e4f258: ldr      x3, [x8, #0x898]
2e4f25c: blr      x9
2e4f260: ldr      x1, [x24]
2e4f264: bl       #0x7af658c
2e4f268: cbz      x21, #0x2e4f3dc
2e4f26c: ldr      w9, [x21, #0x1c]
2e4f270: ldr      x8, [x21, #0x10]
2e4f274: ldr      x25, [x23]
2e4f278: add      w9, w9, #1
2e4f27c: str      w9, [x21, #0x1c]
2e4f280: cbz      x8, #0x2e4f3dc
2e4f284: ldrsw    x9, [x21, #0x18]
2e4f288: ldr      w10, [x8, #0x18]
2e4f28c: mov      x22, x0
2e4f290: mov      x20, x1
2e4f294: cmp      w9, w10
2e4f298: b.hs     #0x2e4f2bc
2e4f29c: add      w10, w9, #1
2e4f2a0: add      x0, x8, x9, lsl #4
2e4f2a4: str      w10, [x21, #0x18]
2e4f2a8: str      x22, [x0, #0x20]!
2e4f2ac: str      x20, [x0, #8]
2e4f2b0: mov      x1, xzr
2e4f2b4: bl       #0x237e114
2e4f2b8: b        #0x2e4f2f4
2e4f2bc: ldr      x8, [x25, #0x20]
2e4f2c0: ldr      x8, [x8, #0xc0]
2e4f2c4: ldr      x3, [x8, #0x58]
2e4f2c8: ldr      x8, [x3, #0x20]
2e4f2cc: cbnz     x8, #0x2e4f2e4
2e4f2d0: ldr      x8, [x3]
2e4f2d4: blr      x8
2e4f2d8: ldr      x8, [x25, #0x20]
2e4f2dc: ldr      x8, [x8, #0xc0]
2e4f2e0: ldr      x3, [x8, #0x58]
2e4f2e4: mov      x0, x21
2e4f2e8: mov      x1, x22
2e4f2ec: mov      x2, x20
2e4f2f0: bl       #0x6f2eff4
2e4f2f4: adrp     x8, #0xc69e000
2e4f2f8: ldr      x8, [x8, #0x560]
2e4f2fc: ldr      x20, [sp, #0x58]
2e4f300: ldr      x0, [x8]
2e4f304: ldr      w8, [x0, #0xe0]
2e4f308: cbnz     w8, #0x2e4f310
2e4f30c: bl       #0x237e260
2e4f310: mov      x0, x20
2e4f314: mov      x1, xzr
2e4f318: mov      x2, xzr
2e4f31c: bl       #0x97a04d8 ; -> UnityEngine.Object.op_Inequality
2e4f320: tbz      w0, #0, #0x2e4f3c0
2e4f324: ldr      x0, [sp, #0x58]
2e4f328: ldr      x1, [x24]
2e4f32c: ldr      x19, [x19, #0x258]
2e4f330: bl       #0x7af658c
2e4f334: cbz      x19, #0x2e4f3dc
2e4f338: ldr      w9, [x19, #0x1c]
2e4f33c: ldr      x8, [x19, #0x10]
2e4f340: ldr      x22, [x23]
2e4f344: add      w9, w9, #1
2e4f348: str      w9, [x19, #0x1c]
2e4f34c: cbz      x8, #0x2e4f3dc
2e4f350: ldrsw    x9, [x19, #0x18]
2e4f354: ldr      w10, [x8, #0x18]
2e4f358: mov      x21, x0
2e4f35c: mov      x20, x1
2e4f360: cmp      w9, w10
2e4f364: b.hs     #0x2e4f388
2e4f368: add      w10, w9, #1
2e4f36c: add      x0, x8, x9, lsl #4
2e4f370: str      w10, [x19, #0x18]
2e4f374: str      x21, [x0, #0x20]!
2e4f378: mov      x1, xzr
2e4f37c: str      x20, [x0, #8]
2e4f380: bl       #0x237e114
2e4f384: b        #0x2e4f3c0
2e4f388: ldr      x8, [x22, #0x20]
2e4f38c: ldr      x8, [x8, #0xc0]
2e4f390: ldr      x3, [x8, #0x58]
2e4f394: ldr      x8, [x3, #0x20]
2e4f398: cbnz     x8, #0x2e4f3b0
2e4f39c: ldr      x8, [x3]
2e4f3a0: blr      x8
2e4f3a4: ldr      x8, [x22, #0x20]
2e4f3a8: ldr      x8, [x8, #0xc0]
2e4f3ac: ldr      x3, [x8, #0x58]
2e4f3b0: mov      x0, x19
2e4f3b4: mov      x1, x21
2e4f3b8: mov      x2, x20
2e4f3bc: bl       #0x6f2eff4
2e4f3c0: ldp      x19, x30, [sp, #0xa0]
2e4f3c4: ldp      x21, x20, [sp, #0x90]
2e4f3c8: ldp      x23, x22, [sp, #0x80]
2e4f3cc: ldp      x25, x24, [sp, #0x70]
2e4f3d0: ldp      d9, d8, [sp, #0x60]
2e4f3d4: add      sp, sp, #0xb0
2e4f3d8: ret      
2e4f3dc: bl       #0x237e284