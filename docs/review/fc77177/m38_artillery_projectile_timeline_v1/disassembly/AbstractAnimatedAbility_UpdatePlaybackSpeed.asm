2ea7e60: sub      sp, sp, #0x60
2ea7e64: str      d10, [sp, #0x10]
2ea7e68: stp      d9, d8, [sp, #0x18]
2ea7e6c: str      x24, [sp, #0x28]
2ea7e70: stp      x23, x22, [sp, #0x30]
2ea7e74: stp      x21, x20, [sp, #0x40]
2ea7e78: stp      x19, x30, [sp, #0x50]
2ea7e7c: adrp     x23, #0xce92000
2ea7e80: adrp     x22, #0xc60c000
2ea7e84: ldrb     w8, [x23, #0x53c]
2ea7e88: ldr      x22, [x22, #0x8a8]
2ea7e8c: mov      x19, x2
2ea7e90: mov      w21, w1
2ea7e94: mov      x20, x0
2ea7e98: tbnz     w8, #0, #0x2ea7ec8
2ea7e9c: adrp     x0, #0xc60c000
2ea7ea0: ldr      x0, [x0, #0x8a8]
2ea7ea4: bl       #0x237e160
2ea7ea8: adrp     x0, #0xc658000
2ea7eac: ldr      x0, [x0, #0x7e8]
2ea7eb0: bl       #0x237e160
2ea7eb4: adrp     x0, #0xc5fb000
2ea7eb8: ldr      x0, [x0, #0xfb0]
2ea7ebc: bl       #0x237e160
2ea7ec0: mov      w8, #1
2ea7ec4: strb     w8, [x23, #0x53c]
2ea7ec8: ldr      x8, [x22]
2ea7ecc: stp      xzr, xzr, [sp]
2ea7ed0: ldr      x8, [x8, #0xb8]
2ea7ed4: ldr      x0, [x8, #0x118]
2ea7ed8: cbz      x0, #0x2ea7ef4
2ea7edc: mov      x1, x20
2ea7ee0: mov      w2, w21
2ea7ee4: mov      x3, x19
2ea7ee8: mov      x4, xzr
2ea7eec: bl       #0x4fbae04 ; -> XLua.DelegateBridge.__Gen_Delegate_Imp2655
2ea7ef0: b        #0x2ea81f8
2ea7ef4: sub      w8, w21, #1
2ea7ef8: cmp      w8, #1
2ea7efc: b.hi     #0x2ea7f10
2ea7f00: mov      w8, #0x3f800000
2ea7f04: mov      w0, wzr
2ea7f08: str      w8, [x19]
2ea7f0c: b        #0x2ea81f8
2ea7f10: adrp     x24, #0xc677000
2ea7f14: ldr      x24, [x24, #0x6d0]
2ea7f18: ldrb     w8, [x24]
2ea7f1c: cbz      w8, #0x2ea7f28
2ea7f20: ldr      x0, [x20]
2ea7f24: bl       #0x23c9be0
2ea7f28: ldr      x8, [x20]
2ea7f2c: mov      x0, x20
2ea7f30: ldr      x9, [x8, #0x250]
2ea7f34: ldr      x1, [x8, #0x258]
2ea7f38: blr      x9
2ea7f3c: str      x0, [x20, #0x1b0]
2ea7f40: fmov     v0.2s, #1.00000000
2ea7f44: mov      x0, x20
2ea7f48: mov      x1, xzr
2ea7f4c: str      d0, [x20, #0x1b8]
2ea7f50: bl       #0x254f33c ; -> Torappu.Battle.Ability.get_owner
2ea7f54: cbz      x0, #0x2ea821c
2ea7f58: ldrb     w8, [x24]
2ea7f5c: ldr      x22, [x20, #0x148]
2ea7f60: mov      x21, x0
2ea7f64: cbz      w8, #0x2ea7f70
2ea7f68: ldr      x0, [x21]
2ea7f6c: bl       #0x23c9be0
2ea7f70: ldr      x8, [x21]
2ea7f74: adrp     x23, #0xc658000
2ea7f78: add      x2, sp, #0xc
2ea7f7c: add      x3, sp, #8
2ea7f80: ldr      x9, [x8, #0x7e0]
2ea7f84: ldr      x4, [x8, #0x7e8]
2ea7f88: ldr      x23, [x23, #0x7e8]
2ea7f8c: mov      x0, x21
2ea7f90: mov      x1, x22
2ea7f94: blr      x9
2ea7f98: tbz      w0, #0, #0x2ea8170
2ea7f9c: ldrb     w8, [x24]
2ea7fa0: cbz      w8, #0x2ea7fac
2ea7fa4: ldr      x0, [x20]
2ea7fa8: bl       #0x23c9be0
2ea7fac: ldr      x8, [x20]
2ea7fb0: mov      x0, x20
2ea7fb4: ldr      x9, [x8, #0x210]
2ea7fb8: ldr      x1, [x8, #0x218]
2ea7fbc: blr      x9
2ea7fc0: tbz      w0, #0, #0x2ea80a0
2ea7fc4: mov      x0, x20
2ea7fc8: mov      x1, xzr
2ea7fcc: bl       #0x254f33c ; -> Torappu.Battle.Ability.get_owner
2ea7fd0: cbz      x0, #0x2ea821c
2ea7fd4: mov      x1, xzr
2ea7fd8: bl       #0x266f5c0 ; -> Torappu.Battle.Entity.get_slowDown
2ea7fdc: ldr      x8, [x23]
2ea7fe0: mov      x21, x0
2ea7fe4: ldr      w9, [x8, #0xe0]
2ea7fe8: cbnz     w9, #0x2ea7ff8
2ea7fec: mov      x0, x8
2ea7ff0: bl       #0x237e260
2ea7ff4: ldr      x8, [x23]
2ea7ff8: ldr      x8, [x8, #0xb8]
2ea7ffc: mov      x0, x21
2ea8000: mov      x2, xzr
2ea8004: ldr      x1, [x8, #0x20]
2ea8008: bl       #0x9510f24 ; -> Torappu.FP.op_Inequality
2ea800c: tbz      w0, #0, #0x2ea80a0
2ea8010: ldr      w8, [x20, #0x140]
2ea8014: cmp      w8, #1
2ea8018: b.ne     #0x2ea8098
2ea801c: ldr      s8, [sp, #8]
2ea8020: mov      x0, x20
2ea8024: mov      x1, xzr
2ea8028: bl       #0x254f33c ; -> Torappu.Battle.Ability.get_owner
2ea802c: cbz      x0, #0x2ea821c
2ea8030: mov      x1, xzr
2ea8034: bl       #0x266f64c ; -> Torappu.Battle.Entity.get_animSlowDown
2ea8038: ldr      x8, [x23]
2ea803c: str      x0, [sp]
2ea8040: ldr      w9, [x8, #0xe0]
2ea8044: cbnz     w9, #0x2ea8050
2ea8048: mov      x0, x8
2ea804c: bl       #0x237e260
2ea8050: mov      x0, sp
2ea8054: mov      x1, xzr
2ea8058: bl       #0x950fe14 ; -> Torappu.FP.AsFloat
2ea805c: ldr      s9, [sp, #0xc]
2ea8060: fmul     s0, s8, s0
2ea8064: mov      x0, x20
2ea8068: mov      x1, xzr
2ea806c: str      s0, [sp, #8]
2ea8070: bl       #0x254f33c ; -> Torappu.Battle.Ability.get_owner
2ea8074: cbz      x0, #0x2ea821c
2ea8078: mov      x1, xzr
2ea807c: bl       #0x266f64c ; -> Torappu.Battle.Entity.get_animSlowDown
2ea8080: str      x0, [sp]
2ea8084: mov      x0, sp
2ea8088: mov      x1, xzr
2ea808c: bl       #0x950fe14 ; -> Torappu.FP.AsFloat
2ea8090: fdiv     s0, s9, s0
2ea8094: str      s0, [sp, #0xc]
2ea8098: mov      w22, #1
2ea809c: b        #0x2ea80a4
2ea80a0: mov      w22, wzr
2ea80a4: ldr      w8, [sp, #8]
2ea80a8: add      x21, x20, #0x1b0
2ea80ac: str      w8, [x20, #0x1bc]
2ea80b0: ldr      x0, [x23]
2ea80b4: ldr      w8, [x0, #0xe0]
2ea80b8: cbnz     w8, #0x2ea80c0
2ea80bc: bl       #0x237e260
2ea80c0: mov      x0, x21
2ea80c4: mov      x1, xzr
2ea80c8: bl       #0x950fe14 ; -> Torappu.FP.AsFloat
2ea80cc: ldr      s9, [sp, #0xc]
2ea80d0: adrp     x8, #0x99db000
2ea80d4: ldr      s1, [x8, #0x49c]
2ea80d8: ldr      s8, [x20, #0x1a0]
2ea80dc: fdiv     s0, s0, s9
2ea80e0: fmaxnm   s10, s0, s1
2ea80e4: fcmp     s8, #0.0
2ea80e8: str      s10, [x20, #0x1b8]
2ea80ec: b.lt     #0x2ea8150
2ea80f0: cbz      w22, #0x2ea8144
2ea80f4: mov      x0, x20
2ea80f8: mov      x1, xzr
2ea80fc: bl       #0x254f33c ; -> Torappu.Battle.Ability.get_owner
2ea8100: cbz      x0, #0x2ea821c
2ea8104: mov      x1, xzr
2ea8108: bl       #0x266f64c ; -> Torappu.Battle.Entity.get_animSlowDown
2ea810c: ldr      x8, [x23]
2ea8110: str      x0, [sp]
2ea8114: ldr      w9, [x8, #0xe0]
2ea8118: cbnz     w9, #0x2ea8124
2ea811c: mov      x0, x8
2ea8120: bl       #0x237e260
2ea8124: mov      x0, sp
2ea8128: mov      x1, xzr
2ea812c: bl       #0x950fe14 ; -> Torappu.FP.AsFloat
2ea8130: ldr      s10, [x20, #0x1b8]
2ea8134: ldr      s9, [sp, #0xc]
2ea8138: fdiv     s0, s8, s0
2ea813c: fmov     s1, #2.50000000
2ea8140: fmin     s8, s0, s1
2ea8144: fcmp     s10, s8
2ea8148: fcsel    s10, s10, s8, mi
2ea814c: str      s10, [x20, #0x1b8]
2ea8150: ldr      x0, [x23]
2ea8154: ldr      w8, [x0, #0xe0]
2ea8158: cbnz     w8, #0x2ea8160
2ea815c: bl       #0x237e260
2ea8160: fmul     s0, s9, s10
2ea8164: mov      x0, xzr
2ea8168: bl       #0x950ffe8 ; -> Torappu.FP.op_Implicit
2ea816c: str      x0, [x20, #0x1b0]
2ea8170: mov      x0, x20
2ea8174: bl       #0x2ea8220 ; -> Torappu.Battle.Abilities.EasyToStartAbility.get_waitForAttackEvent
2ea8178: ldr      x21, [x20, #0x1b0]
2ea817c: tbnz     w0, #0, #0x2ea81d8
2ea8180: ldr      x0, [x23]
2ea8184: adrp     x22, #0xc5fb000
2ea8188: ldr      s8, [x20, #0x188]
2ea818c: ldr      s9, [x20, #0x1b8]
2ea8190: ldr      w8, [x0, #0xe0]
2ea8194: ldr      x22, [x22, #0xfb0]
2ea8198: cbnz     w8, #0x2ea81a0
2ea819c: bl       #0x237e260
2ea81a0: fmul     s0, s8, s9
2ea81a4: mov      x0, xzr
2ea81a8: bl       #0x950ffe8 ; -> Torappu.FP.op_Implicit
2ea81ac: ldr      x8, [x22]
2ea81b0: mov      x22, x0
2ea81b4: ldr      w9, [x8, #0xe0]
2ea81b8: cbnz     w9, #0x2ea81c4
2ea81bc: mov      x0, x8
2ea81c0: bl       #0x237e260
2ea81c4: mov      x0, x21
2ea81c8: mov      x1, x22
2ea81cc: mov      x2, xzr
2ea81d0: bl       #0x95133e8 ; -> Torappu.TSMath.Min
2ea81d4: mov      x21, x0
2ea81d8: str      x21, [x20, #0x1a8]
2ea81dc: ldr      s0, [x20, #0x1b8]
2ea81e0: ldr      s1, [sp, #8]
2ea81e4: fmov     s2, #1.00000000
2ea81e8: mov      w0, #1
2ea81ec: fdiv     s0, s2, s0
2ea81f0: fmul     s0, s0, s1
2ea81f4: str      s0, [x19]
2ea81f8: ldp      x19, x30, [sp, #0x50]
2ea81fc: ldp      x21, x20, [sp, #0x40]
2ea8200: ldp      x23, x22, [sp, #0x30]
2ea8204: ldr      x24, [sp, #0x28]
2ea8208: ldp      d9, d8, [sp, #0x18]
2ea820c: ldr      d10, [sp, #0x10]
2ea8210: and      w0, w0, #1
2ea8214: add      sp, sp, #0x60
2ea8218: ret      
2ea821c: bl       #0x237e284