257ec94: str      x24, [sp, #-0x40]!
257ec98: stp      x23, x22, [sp, #0x10]
257ec9c: stp      x21, x20, [sp, #0x20]
257eca0: stp      x19, x30, [sp, #0x30]
257eca4: adrp     x23, #0xce8c000
257eca8: adrp     x24, #0xc666000
257ecac: ldrb     w8, [x23, #0xd63]
257ecb0: ldr      x24, [x24, #0xa88]
257ecb4: mov      x19, x3
257ecb8: mov      x20, x2
257ecbc: mov      x21, x1
257ecc0: mov      x22, x0
257ecc4: tbnz     w8, #0, #0x257ecdc
257ecc8: adrp     x0, #0xc666000
257eccc: ldr      x0, [x0, #0xa88]
257ecd0: bl       #0x237e160
257ecd4: mov      w8, #1
257ecd8: strb     w8, [x23, #0xd63]
257ecdc: ldr      x8, [x24]
257ece0: ldr      x8, [x8, #0xb8]
257ece4: ldr      x0, [x8, #0xc8]
257ece8: cbz      x0, #0x257ed14
257ecec: mov      x1, x22
257ecf0: mov      x2, x21
257ecf4: mov      x3, x20
257ecf8: mov      x4, x19
257ecfc: ldp      x19, x30, [sp, #0x30]
257ed00: ldp      x21, x20, [sp, #0x20]
257ed04: ldp      x23, x22, [sp, #0x10]
257ed08: mov      x5, xzr
257ed0c: ldr      x24, [sp], #0x40
257ed10: b        #0x4fbe7ac ; -> XLua.DelegateBridge.__Gen_Delegate_Imp2681
257ed14: adrp     x8, #0xc677000
257ed18: ldr      x8, [x8, #0x6d0]
257ed1c: ldrb     w8, [x8]
257ed20: cbz      w8, #0x257ed2c
257ed24: ldr      x0, [x22]
257ed28: bl       #0x23c9be0
257ed2c: ldr      x8, [x22]
257ed30: mov      w2, #1
257ed34: mov      x0, x22
257ed38: mov      x1, x21
257ed3c: ldr      x9, [x8, #0x500]
257ed40: ldr      x3, [x8, #0x508]
257ed44: blr      x9
257ed48: cbz      x0, #0x257ed68
257ed4c: ldr      s0, [x0, #0x2c]
257ed50: ldr      s1, [x0, #0x24]
257ed54: fdiv     s0, s0, s1
257ed58: str      s0, [x20]
257ed5c: ldr      w8, [x0, #0x24]
257ed60: mov      w0, #1
257ed64: b        #0x257ed70
257ed68: mov      w8, #0x3f800000
257ed6c: str      wzr, [x20]
257ed70: str      w8, [x19]
257ed74: ldp      x19, x30, [sp, #0x30]
257ed78: ldp      x21, x20, [sp, #0x20]
257ed7c: ldp      x23, x22, [sp, #0x10]
257ed80: ldr      x24, [sp], #0x40
257ed84: ret      