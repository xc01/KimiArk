2e541fc: sub      sp, sp, #0xa0
2e54200: stp      d9, d8, [sp, #0x60]
2e54204: str      x22, [sp, #0x70]
2e54208: stp      x21, x20, [sp, #0x80]
2e5420c: stp      x19, x30, [sp, #0x90]
2e54210: adrp     x21, #0xce92000
2e54214: adrp     x22, #0xc685000
2e54218: ldrb     w8, [x21, #0x24e]
2e5421c: ldr      x22, [x22, #0x308]
2e54220: mov      x19, x1
2e54224: mov      x20, x0
2e54228: tbnz     w8, #0, #0x2e54258
2e5422c: adrp     x0, #0xc6bb000
2e54230: ldr      x0, [x0, #0x258]
2e54234: bl       #0x237e160
2e54238: adrp     x0, #0xc663000
2e5423c: ldr      x0, [x0, #0xbb0]
2e54240: bl       #0x237e160
2e54244: adrp     x0, #0xc685000
2e54248: ldr      x0, [x0, #0x308]
2e5424c: bl       #0x237e160
2e54250: mov      w8, #1
2e54254: strb     w8, [x21, #0x24e]
2e54258: ldr      x8, [x22]
2e5425c: ldr      x8, [x8, #0xb8]
2e54260: ldr      x0, [x8, #0x70]
2e54264: cbz      x0, #0x2e5428c
2e54268: mov      x1, x20
2e5426c: mov      x2, x19
2e54270: ldp      x19, x30, [sp, #0x90]
2e54274: ldp      x21, x20, [sp, #0x80]
2e54278: ldr      x22, [sp, #0x70]
2e5427c: ldp      d9, d8, [sp, #0x60]
2e54280: mov      x3, xzr
2e54284: add      sp, sp, #0xa0
2e54288: b        #0x50b3d08 ; -> XLua.DelegateBridge.__Gen_Delegate_Imp4414
2e5428c: ldr      w8, [x20, #0x238]
2e54290: sub      w8, w8, #1
2e54294: cmp      w8, #3
2e54298: b.hi     #0x2e543f4
2e5429c: adrp     x9, #0x99e4000
2e542a0: add      x9, x9, #0x5f
2e542a4: adrp     x21, #0xc6bb000
2e542a8: adr      x10, #0x2e542bc
2e542ac: ldrb     w11, [x9, x8]
2e542b0: add      x10, x10, x11, lsl #2
2e542b4: ldr      x21, [x21, #0x258]
2e542b8: br       x10
2e542bc: ldp      s0, s1, [x20, #0xe0]
2e542c0: movi     v2.2d, #0000000000000000
2e542c4: add      x0, sp, #0x30
2e542c8: mov      x1, xzr
2e542cc: str      xzr, [sp, #0x50]
2e542d0: stp      q2, q2, [sp, #0x30]
2e542d4: bl       #0x268695c ; -> Torappu.Battle.FixedPosition..ctor
2e542d8: b        #0x2e543c0
2e542dc: cbz      x19, #0x2e54418
2e542e0: adrp     x8, #0xc677000
2e542e4: ldr      x8, [x8, #0x6d0]
2e542e8: ldrb     w8, [x8]
2e542ec: cbz      w8, #0x2e542f8
2e542f0: ldr      x0, [x19]
2e542f4: bl       #0x23c9be0
2e542f8: ldr      x8, [x19]
2e542fc: mov      x0, x19
2e54300: ldr      x9, [x8, #0x480]
2e54304: ldr      x1, [x8, #0x488]
2e54308: blr      x9
2e5430c: mov      x1, x0
2e54310: movi     v0.2d, #0000000000000000
2e54314: add      x0, sp, #0x30
2e54318: mov      x2, xzr
2e5431c: str      xzr, [sp, #0x50]
2e54320: stp      q0, q0, [sp, #0x30]
2e54324: bl       #0x2686b3c ; -> Torappu.Battle.FixedPosition..ctor
2e54328: b        #0x2e543c0
2e5432c: cbz      x19, #0x2e54418
2e54330: mov      x0, x19
2e54334: mov      x1, xzr
2e54338: bl       #0x2a5bfd4 ; -> Torappu.Battle.VisualObject.get_mapPositionV3
2e5433c: movi     v3.2d, #0000000000000000
2e54340: add      x0, sp, #0x30
2e54344: str      xzr, [sp, #0x50]
2e54348: stp      q3, q3, [sp, #0x30]
2e5434c: b        #0x2e543b8
2e54350: cbz      x19, #0x2e54418
2e54354: mov      x0, x19
2e54358: mov      x1, xzr
2e5435c: bl       #0x2a5bfd4 ; -> Torappu.Battle.VisualObject.get_mapPositionV3
2e54360: adrp     x8, #0xc677000
2e54364: ldr      x8, [x8, #0x6d0]
2e54368: mov      v8.16b, v0.16b
2e5436c: mov      v9.16b, v1.16b
2e54370: ldrb     w8, [x8]
2e54374: cbz      w8, #0x2e54380
2e54378: ldr      x0, [x19]
2e5437c: bl       #0x23c9be0
2e54380: ldr      x8, [x19]
2e54384: mov      x0, x19
2e54388: ldr      x9, [x8, #0x480]
2e5438c: ldr      x1, [x8, #0x488]
2e54390: blr      x9
2e54394: cbz      x0, #0x2e54418
2e54398: mov      x1, xzr
2e5439c: bl       #0x2a5bfd4 ; -> Torappu.Battle.VisualObject.get_mapPositionV3
2e543a0: movi     v0.2d, #0000000000000000
2e543a4: str      xzr, [sp, #0x50]
2e543a8: stp      q0, q0, [sp, #0x30]
2e543ac: add      x0, sp, #0x30
2e543b0: mov      v0.16b, v8.16b
2e543b4: mov      v1.16b, v9.16b
2e543b8: mov      x1, xzr
2e543bc: bl       #0x2686ab0 ; -> Torappu.Battle.FixedPosition..ctor
2e543c0: ldp      q0, q1, [sp, #0x30]
2e543c4: ldr      x8, [sp, #0x50]
2e543c8: ldr      x0, [x21]
2e543cc: mov      x1, sp
2e543d0: stp      q0, q1, [sp]
2e543d4: str      x8, [sp, #0x20]
2e543d8: bl       #0x237e268
2e543dc: ldp      x19, x30, [sp, #0x90]
2e543e0: ldp      x21, x20, [sp, #0x80]
2e543e4: ldr      x22, [sp, #0x70]
2e543e8: ldp      d9, d8, [sp, #0x60]
2e543ec: add      sp, sp, #0xa0
2e543f0: ret      
2e543f4: cbz      x19, #0x2e54418
2e543f8: mov      x0, x19
2e543fc: ldp      x19, x30, [sp, #0x90]
2e54400: ldp      x21, x20, [sp, #0x80]
2e54404: ldr      x22, [sp, #0x70]
2e54408: ldp      d9, d8, [sp, #0x60]
2e5440c: mov      x1, xzr
2e54410: add      sp, sp, #0xa0
2e54414: b        #0x266c9e8 ; -> Torappu.Battle.Entity.get_hitMountPoint
2e54418: bl       #0x237e284