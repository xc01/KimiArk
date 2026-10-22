25544d4: sub      sp, sp, #0x70
25544d8: stp      d9, d8, [sp, #0x20]
25544dc: str      x24, [sp, #0x30]
25544e0: stp      x23, x22, [sp, #0x40]
25544e4: stp      x21, x20, [sp, #0x50]
25544e8: stp      x19, x30, [sp, #0x60]
25544ec: adrp     x23, #0xce8c000
25544f0: adrp     x24, #0xc650000
25544f4: ldrb     w8, [x23, #0xb87]
25544f8: ldr      x24, [x24, #0xc20]
25544fc: mov      w22, w3
2554500: mov      x20, x2
2554504: mov      x21, x1
2554508: mov      x19, x0
255450c: tbnz     w8, #0, #0x2554560
2554510: adrp     x0, #0xc650000
2554514: ldr      x0, [x0, #0xc20]
2554518: bl       #0x237e160
255451c: adrp     x0, #0xc726000
2554520: ldr      x0, [x0, #0x470]
2554524: bl       #0x237e160
2554528: adrp     x0, #0xc6e1000
255452c: ldr      x0, [x0, #0xc0]
2554530: bl       #0x237e160
2554534: adrp     x0, #0xc730000
2554538: ldr      x0, [x0, #0xd58]
255453c: bl       #0x237e160
2554540: adrp     x0, #0xc66a000
2554544: ldr      x0, [x0, #0xd70]
2554548: bl       #0x237e160
255454c: adrp     x0, #0xc69e000
2554550: ldr      x0, [x0, #0x560]
2554554: bl       #0x237e160
2554558: mov      w8, #1
255455c: strb     w8, [x23, #0xb87]
2554560: ldr      x8, [x24]
2554564: ldr      x8, [x8, #0xb8]
2554568: ldr      x0, [x8, #0x90]
255456c: cbz      x0, #0x25545a0
2554570: and      w4, w22, #1
2554574: mov      x1, x19
2554578: mov      x2, x21
255457c: mov      x3, x20
2554580: ldp      x19, x30, [sp, #0x60]
2554584: ldp      x21, x20, [sp, #0x50]
2554588: ldp      x23, x22, [sp, #0x40]
255458c: ldr      x24, [sp, #0x30]
2554590: ldp      d9, d8, [sp, #0x20]
2554594: mov      x5, xzr
2554598: add      sp, sp, #0x70
255459c: b        #0x4ea9bd8 ; -> XLua.DelegateBridge.__Gen_Delegate_Imp664
25545a0: adrp     x24, #0xc69e000
25545a4: ldr      x24, [x24, #0x560]
25545a8: ldr      x0, [x24]
25545ac: ldr      w8, [x0, #0xe0]
25545b0: cbnz     w8, #0x25545b8
25545b4: bl       #0x237e260
25545b8: mov      x0, x21
25545bc: mov      x1, xzr
25545c0: mov      x2, xzr
25545c4: bl       #0x97a4508 ; -> UnityEngine.Object.op_Equality
25545c8: adrp     x23, #0xc677000
25545cc: ldr      x23, [x23, #0x6d0]
25545d0: tbz      w0, #0, #0x2554640
25545d4: ldrb     w8, [x23]
25545d8: cbz      w8, #0x25545e4
25545dc: ldr      x0, [x19]
25545e0: bl       #0x23c9be0
25545e4: ldr      x8, [x19]
25545e8: mov      x0, x19
25545ec: ldr      x9, [x8, #0x260]
25545f0: ldr      x1, [x8, #0x268]
25545f4: blr      x9
25545f8: tbz      w0, #0, #0x2554640
25545fc: ldrb     w8, [x23]
2554600: cbz      w8, #0x255460c
2554604: ldr      x0, [x19]
2554608: bl       #0x23c9be0
255460c: ldr      x8, [x19]
2554610: and      w2, w22, #1
2554614: mov      x0, x19
2554618: mov      x1, x20
255461c: ldr      x4, [x8, #0x360]
2554620: ldr      x3, [x8, #0x368]
2554624: ldp      x19, x30, [sp, #0x60]
2554628: ldp      x21, x20, [sp, #0x50]
255462c: ldp      x23, x22, [sp, #0x40]
2554630: ldr      x24, [sp, #0x30]
2554634: ldp      d9, d8, [sp, #0x20]
2554638: add      sp, sp, #0x70
255463c: br       x4
2554640: and      w1, w22, #1
2554644: mov      x0, x19
2554648: bl       #0x2554208 ; -> Torappu.Battle.AbilityStandard.set_firstAttack
255464c: ldr      x0, [x24]
2554650: ldr      w8, [x0, #0xe0]
2554654: cbnz     w8, #0x255465c
2554658: bl       #0x237e260
255465c: mov      x0, x21
2554660: mov      x1, xzr
2554664: mov      x2, xzr
2554668: bl       #0x97a4508 ; -> UnityEngine.Object.op_Equality
255466c: tbz      w0, #0, #0x25546b4
2554670: ldrb     w8, [x23]
2554674: cbz      w8, #0x2554680
2554678: ldr      x0, [x19]
255467c: bl       #0x23c9be0
2554680: ldr      x8, [x19]
2554684: mov      x0, x19
2554688: ldr      x9, [x8, #0x580]
255468c: ldr      x1, [x8, #0x588]
2554690: blr      x9
2554694: cmp      w0, #1
2554698: b.ne     #0x25546b4
255469c: adrp     x8, #0xc730000
25546a0: ldr      x8, [x8, #0xd58]
25546a4: add      x0, x19, #0x50
25546a8: ldr      x1, [x8]
25546ac: bl       #0x7af6340
25546b0: mov      x21, x0
25546b4: ldr      x0, [x24]
25546b8: ldr      w8, [x0, #0xe0]
25546bc: cbnz     w8, #0x25546c4
25546c0: bl       #0x237e260
25546c4: mov      x0, x21
25546c8: mov      x1, xzr
25546cc: mov      x2, xzr
25546d0: bl       #0x97a4508 ; -> UnityEngine.Object.op_Equality
25546d4: tbnz     w0, #0, #0x2554884
25546d8: ldrb     w8, [x23]
25546dc: cbz      w8, #0x25546e8
25546e0: ldr      x0, [x19]
25546e4: bl       #0x23c9be0
25546e8: ldr      x8, [x19]
25546ec: mov      x0, x19
25546f0: ldr      x9, [x8, #0x270]
25546f4: ldr      x1, [x8, #0x278]
25546f8: blr      x9
25546fc: tbz      w0, #0, #0x2554884
2554700: mov      x0, x19
2554704: bl       #0x2554440 ; -> Torappu.Battle.AbilityStandard._CheckGameObjectActiveBeforeCast
2554708: tbz      w0, #0, #0x2554884
255470c: ldrb     w8, [x23]
2554710: cbz      w8, #0x255471c
2554714: ldr      x0, [x19]
2554718: bl       #0x23c9be0
255471c: ldr      x8, [x19]
2554720: mov      x0, x19
2554724: ldr      x9, [x8, #0x3f0]
2554728: ldr      x1, [x8, #0x3f8]
255472c: blr      x9
2554730: cbz      x21, #0x25548a4
2554734: adrp     x22, #0xc66a000
2554738: adrp     x24, #0xc6e1000
255473c: ldr      x22, [x22, #0xd70]
2554740: ldr      x24, [x24, #0xc0]
2554744: mov      x0, x21
2554748: mov      x1, xzr
255474c: bl       #0x2a5bfb4 ; -> Torappu.Battle.VisualObject.get_mapPosition
2554750: ldr      x1, [x22]
2554754: mov      x0, x21
2554758: mov      v8.16b, v0.16b
255475c: mov      v9.16b, v1.16b
2554760: bl       #0x64b6ccc
2554764: ldr      x2, [x24]
2554768: add      x8, sp, #8
255476c: mov      v0.16b, v8.16b
2554770: mov      v1.16b, v9.16b
2554774: bl       #0x64a9ed4
2554778: ldr      x8, [sp, #0x18]
255477c: ldur     q0, [sp, #8]
2554780: add      x0, x19, #0xe8
2554784: mov      x1, xzr
2554788: str      x8, [x19, #0xf0]
255478c: str      q0, [x19, #0xe0]
2554790: bl       #0x237e114
2554794: ldrb     w8, [x23]
2554798: cbz      w8, #0x25547a4
255479c: ldr      x0, [x19]
25547a0: bl       #0x23c9be0
25547a4: ldr      x8, [x19]
25547a8: mov      x0, x19
25547ac: ldr      x9, [x8, #0x590]
25547b0: ldr      x1, [x8, #0x598]
25547b4: blr      x9
25547b8: cbz      w0, #0x25547e8
25547bc: ldrb     w8, [x23]
25547c0: cbz      w8, #0x25547cc
25547c4: ldr      x0, [x19]
25547c8: bl       #0x23c9be0
25547cc: ldr      x8, [x19]
25547d0: mov      x0, x19
25547d4: ldr      x9, [x8, #0x590]
25547d8: ldr      x1, [x8, #0x598]
25547dc: blr      x9
25547e0: cmp      w0, #2
25547e4: b.ne     #0x255481c
25547e8: ldrb     w8, [x23]
25547ec: cbz      w8, #0x25547f8
25547f0: ldr      x0, [x19]
25547f4: bl       #0x23c9be0
25547f8: ldr      x8, [x19]
25547fc: mov      x0, x19
2554800: mov      w1, wzr
2554804: ldr      x9, [x8, #0x6d0]
2554808: ldr      x2, [x8, #0x6d8]
255480c: blr      x9
2554810: mov      w8, w0
2554814: mov      w0, wzr
2554818: tbz      w8, #0, #0x2554888
255481c: mov      x0, x19
2554820: mov      x1, x20
2554824: bl       #0x2552fe8 ; -> Torappu.Battle.Ability.RegisterFinishCallbackOnce
2554828: ldr      x0, [x19, #0x70]
255482c: cbz      x0, #0x25548a4
2554830: adrp     x20, #0xc726000
2554834: ldr      x20, [x20, #0x470]
2554838: mov      w1, #1
255483c: mov      x2, xzr
2554840: bl       #0x3d23fb4 ; -> Torappu.PeriodicTimer.Reset
2554844: mov      x0, x19
2554848: bl       #0x25530dc ; -> Torappu.Battle.Ability.StartCastingInternal
255484c: mov      x0, x19
2554850: bl       #0x25548a8 ; -> Torappu.Battle.AbilityStandard._DoCast
2554854: ldr      x8, [x20]
2554858: mov      x20, x0
255485c: ldr      w9, [x8, #0xe0]
2554860: cbnz     w9, #0x255486c
2554864: mov      x0, x8
2554868: bl       #0x237e260
255486c: mov      x0, x19
2554870: mov      x1, x20
2554874: mov      x2, xzr
2554878: bl       #0x25adf54 ; -> Torappu.Battle.BattleController.StartBattleCoroutine
255487c: mov      w0, #1
2554880: b        #0x2554888
2554884: mov      w0, wzr
2554888: ldp      x19, x30, [sp, #0x60]
255488c: ldp      x21, x20, [sp, #0x50]
2554890: ldp      x23, x22, [sp, #0x40]
2554894: ldr      x24, [sp, #0x30]
2554898: ldp      d9, d8, [sp, #0x20]
255489c: add      sp, sp, #0x70
25548a0: ret      
25548a4: bl       #0x237e284