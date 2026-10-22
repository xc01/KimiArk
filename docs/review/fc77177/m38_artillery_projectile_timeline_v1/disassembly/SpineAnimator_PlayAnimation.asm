257e5e0: str      d10, [sp, #-0x50]!
257e5e4: stp      d9, d8, [sp, #0x10]
257e5e8: stp      x23, x22, [sp, #0x20]
257e5ec: stp      x21, x20, [sp, #0x30]
257e5f0: stp      x19, x30, [sp, #0x40]
257e5f4: adrp     x22, #0xce8c000
257e5f8: adrp     x23, #0xc666000
257e5fc: ldrb     w8, [x22, #0xd73]
257e600: ldr      x23, [x23, #0xa88]
257e604: mov      v8.16b, v0.16b
257e608: mov      w21, w2
257e60c: mov      x19, x1
257e610: mov      x20, x0
257e614: tbnz     w8, #0, #0x257e638
257e618: adrp     x0, #0xc63c000
257e61c: ldr      x0, [x0, #0x100]
257e620: bl       #0x237e160
257e624: adrp     x0, #0xc666000
257e628: ldr      x0, [x0, #0xa88]
257e62c: bl       #0x237e160
257e630: mov      w8, #1
257e634: strb     w8, [x22, #0xd73]
257e638: ldr      x8, [x23]
257e63c: ldr      x8, [x8, #0xb8]
257e640: ldr      x0, [x8, #0x148]
257e644: cbz      x0, #0x257e674
257e648: and      w3, w21, #1
257e64c: mov      x1, x20
257e650: mov      x2, x19
257e654: mov      v0.16b, v8.16b
257e658: ldp      x19, x30, [sp, #0x40]
257e65c: ldp      x21, x20, [sp, #0x30]
257e660: ldp      x23, x22, [sp, #0x20]
257e664: ldp      d9, d8, [sp, #0x10]
257e668: mov      x4, xzr
257e66c: ldr      d10, [sp], #0x50
257e670: b        #0x4fbdc7c ; -> XLua.DelegateBridge.__Gen_Delegate_Imp2676
257e674: fmov     s9, wzr
257e678: cbz      x19, #0x257e918
257e67c: ldrb     w8, [x19, #0x30]
257e680: cbz      w8, #0x257e918
257e684: ldr      x0, [x19, #0x18]
257e688: mov      x1, xzr
257e68c: bl       #0x8b911d8 ; -> System.String.IsNullOrEmpty
257e690: tbnz     w0, #0, #0x257e918
257e694: str      s8, [x20, #0xe0]
257e698: ldr      x1, [x19, #0x10]
257e69c: mov      x0, x20
257e6a0: str      x1, [x0, #0xd8]!
257e6a4: bl       #0x237e114
257e6a8: adrp     x23, #0xc677000
257e6ac: ldr      x23, [x23, #0x6d0]
257e6b0: ldr      s10, [x19, #0x24]
257e6b4: ldrb     w8, [x23]
257e6b8: cbz      w8, #0x257e6c4
257e6bc: ldr      x0, [x20]
257e6c0: bl       #0x23c9be0
257e6c4: ldr      x8, [x20]
257e6c8: mov      x0, x20
257e6cc: ldr      x9, [x8, #0x480]
257e6d0: ldr      x1, [x8, #0x488]
257e6d4: blr      x9
257e6d8: cbz      x0, #0x257ea9c
257e6dc: adrp     x8, #0xc63c000
257e6e0: ldr      x8, [x8, #0x100]
257e6e4: ldr      s9, [x0, #0x13c]
257e6e8: fmul     s8, s10, s8
257e6ec: ldr      x8, [x8]
257e6f0: ldr      w9, [x8, #0xe0]
257e6f4: cbnz     w9, #0x257e700
257e6f8: mov      x0, x8
257e6fc: bl       #0x237e260
257e700: mov      v0.16b, v9.16b
257e704: mov      v1.16b, v8.16b
257e708: mov      x0, xzr
257e70c: bl       #0x9508458 ; -> Torappu.MathUtil.Equals
257e710: tbnz     w0, #0, #0x257e740
257e714: ldrb     w8, [x23]
257e718: cbz      w8, #0x257e724
257e71c: ldr      x0, [x20]
257e720: bl       #0x23c9be0
257e724: ldr      x8, [x20]
257e728: mov      x0, x20
257e72c: ldr      x9, [x8, #0x480]
257e730: ldr      x1, [x8, #0x488]
257e734: blr      x9
257e738: cbz      x0, #0x257ea9c
257e73c: str      s8, [x0, #0x13c]
257e740: ldr      x0, [x20, #0x90]
257e744: cbz      x0, #0x257ea9c
257e748: mov      v0.16b, v8.16b
257e74c: mov      x1, xzr
257e750: bl       #0x25c5f1c ; -> Torappu.Battle.BakeMuzzleController.OnUpdateTimeScale
257e754: ldrb     w8, [x23]
257e758: cbz      w8, #0x257e764
257e75c: ldr      x0, [x20]
257e760: bl       #0x23c9be0
257e764: ldr      x8, [x20]
257e768: mov      x0, x20
257e76c: ldr      x9, [x8, #0x480]
257e770: ldr      x1, [x8, #0x488]
257e774: blr      x9
257e778: cbz      x0, #0x257ea9c
257e77c: ldrb     w8, [x19, #0x20]
257e780: strb     w8, [x0, #0x138]
257e784: ldrb     w8, [x23]
257e788: cbz      w8, #0x257e794
257e78c: ldr      x0, [x20]
257e790: bl       #0x23c9be0
257e794: ldr      x8, [x20]
257e798: mov      x0, x20
257e79c: ldr      x9, [x8, #0x480]
257e7a0: ldr      x1, [x8, #0x488]
257e7a4: blr      x9
257e7a8: cbz      x0, #0x257ea9c
257e7ac: mov      x1, xzr
257e7b0: bl       #0x8f62b08 ; -> Spine.Unity.SkeletonRenderer.Torappu_GetEnable
257e7b4: tbz      w0, #0, #0x257e7f4
257e7b8: ldrb     w8, [x20, #0x6d]
257e7bc: cbz      w8, #0x257e7f4
257e7c0: ldrb     w8, [x23]
257e7c4: cbz      w8, #0x257e7d0
257e7c8: ldr      x0, [x20]
257e7cc: bl       #0x23c9be0
257e7d0: ldr      x8, [x20]
257e7d4: mov      x0, x20
257e7d8: ldr      x9, [x8, #0x480]
257e7dc: ldr      x1, [x8, #0x488]
257e7e0: blr      x9
257e7e4: cbz      x0, #0x257ea9c
257e7e8: ldrb     w1, [x19, #0x20]
257e7ec: mov      x2, xzr
257e7f0: bl       #0x8f599bc ; -> Spine.Unity.SkeletonAnimation.set_cacheFixedBoundsCenterOnce
257e7f4: mov      x0, x20
257e7f8: mov      x1, x19
257e7fc: bl       #0x2580e3c ; -> Torappu.Battle.SpineAnimator.GetAnimName
257e800: ldrb     w8, [x23]
257e804: mov      x22, x0
257e808: cbz      w8, #0x257e814
257e80c: ldr      x0, [x20]
257e810: bl       #0x23c9be0
257e814: ldr      x8, [x20]
257e818: ldr      x1, [x8, #0x488]
257e81c: ldr      x9, [x8, #0x480]
257e820: mov      x0, x20
257e824: blr      x9
257e828: cbz      x0, #0x257e934
257e82c: mov      x1, xzr
257e830: bl       #0x8f59f34 ; -> Spine.Unity.SkeletonAnimation.get_AnimationName
257e834: mov      x1, x0
257e838: ldrb     w3, [x19, #0x20]
257e83c: mov      x0, x20
257e840: mov      x2, x22
257e844: bl       #0x2580f4c ; -> Torappu.Battle.SpineAnimator.TryApplyCustomMixAnimSettings
257e848: tbnz     w0, #0, #0x257e910
257e84c: ldrb     w8, [x23]
257e850: cbz      w8, #0x257e85c
257e854: ldr      x0, [x20]
257e858: bl       #0x23c9be0
257e85c: ldr      x8, [x20]
257e860: ldr      x1, [x8, #0x488]
257e864: ldr      x9, [x8, #0x480]
257e868: mov      x0, x20
257e86c: blr      x9
257e870: cbz      x0, #0x257e938
257e874: mov      x1, x22
257e878: mov      x2, xzr
257e87c: bl       #0x8f59f7c ; -> Spine.Unity.SkeletonAnimation.set_AnimationName
257e880: ldr      x0, [x20, #0x90]
257e884: cbz      x0, #0x257e93c
257e888: ldrb     w1, [x19, #0x20]
257e88c: mov      x2, xzr
257e890: bl       #0x25c3ec0 ; -> Torappu.Battle.BakeMuzzleController.set_loop
257e894: ldr      x0, [x20, #0x90]
257e898: cbz      x0, #0x257e940
257e89c: mov      x1, x22
257e8a0: mov      x2, xzr
257e8a4: bl       #0x25c3ae0 ; -> Torappu.Battle.BakeMuzzleController.set_animationName
257e8a8: tbz      w21, #0, #0x257e910
257e8ac: ldrb     w8, [x19, #0x20]
257e8b0: cbnz     w8, #0x257e910
257e8b4: ldrb     w8, [x23]
257e8b8: cbz      w8, #0x257e8c4
257e8bc: ldr      x0, [x20]
257e8c0: bl       #0x23c9be0
257e8c4: ldr      x8, [x20]
257e8c8: ldr      x1, [x8, #0x488]
257e8cc: ldr      x9, [x8, #0x480]
257e8d0: mov      x0, x20
257e8d4: blr      x9
257e8d8: cbz      x0, #0x257e944
257e8dc: ldr      x0, [x0, #0x100]
257e8e0: cbz      x0, #0x257e948
257e8e4: ldrb     w3, [x19, #0x20]
257e8e8: mov      w1, wzr
257e8ec: mov      x2, x22
257e8f0: mov      x4, xzr
257e8f4: bl       #0x8f2331c ; -> Spine.AnimationState.SetAnimation
257e8f8: ldr      x0, [x20, #0x90]
257e8fc: cbz      x0, #0x257e94c
257e900: ldrb     w2, [x19, #0x20]
257e904: mov      x1, x22
257e908: mov      x3, xzr
257e90c: bl       #0x25c3be4 ; -> Torappu.Battle.BakeMuzzleController.OnSetAnimation
257e910: ldr      s0, [x19, #0x2c]
257e914: fdiv     s9, s0, s8
257e918: mov      v0.16b, v9.16b
257e91c: ldp      x19, x30, [sp, #0x40]
257e920: ldp      x21, x20, [sp, #0x30]
257e924: ldp      x23, x22, [sp, #0x20]
257e928: ldp      d9, d8, [sp, #0x10]
257e92c: ldr      d10, [sp], #0x50
257e930: ret      
257e934: bl       #0x237e284
257e938: bl       #0x237e284
257e93c: bl       #0x237e284
257e940: bl       #0x237e284
257e944: bl       #0x237e284
257e948: bl       #0x237e284
257e94c: bl       #0x237e284
257e950: b        #0x257e97c
257e954: b        #0x257e97c
257e958: b        #0x257e97c
257e95c: b        #0x257e97c
257e960: b        #0x257e97c
257e964: b        #0x257e97c
257e968: b        #0x257e97c
257e96c: b        #0x257e97c
257e970: b        #0x257e97c
257e974: b        #0x257e97c
257e978: b        #0x257e97c
257e97c: mov      x21, x0
257e980: cmp      w1, #1
257e984: b.ne     #0x257eac8
257e988: mov      x0, x21
257e98c: bl       #0x1d4bde0
257e990: mov      x21, x0
257e994: adrp     x0, #0xc65e000
257e998: ldr      x0, [x0, #0x7e0]
257e99c: bl       #0x237e174
257e9a0: ldr      x8, [x21]
257e9a4: ldr      x1, [x8]
257e9a8: bl       #0x237e5a8
257e9ac: tbz      w0, #0, #0x257eaa0
257e9b0: bl       #0x1d4cd30
257e9b4: mov      x0, x20
257e9b8: bl       #0x257f218 ; -> Torappu.Battle.UnitAnimator.get_host
257e9bc: mov      x21, x0
257e9c0: adrp     x0, #0xc69e000
257e9c4: ldr      x0, [x0, #0x560]
257e9c8: bl       #0x237e174
257e9cc: ldr      w8, [x0, #0xe0]
257e9d0: cbnz     w8, #0x257e9d8
257e9d4: bl       #0x237e260
257e9d8: mov      x0, x21
257e9dc: mov      x1, xzr
257e9e0: mov      x2, xzr
257e9e4: bl       #0x97a04d8 ; -> UnityEngine.Object.op_Inequality
257e9e8: ldr      x21, [x19, #0x10]
257e9ec: tbz      w0, #0, #0x257ea40
257e9f0: mov      x0, x20
257e9f4: bl       #0x257f218 ; -> Torappu.Battle.UnitAnimator.get_host
257e9f8: cbz      x0, #0x257ea9c
257e9fc: mov      x1, xzr
257ea00: bl       #0x97a4780 ; -> UnityEngine.Object.get_name
257ea04: mov      x20, x0
257ea08: adrp     x0, #0xc6f1000
257ea0c: ldr      x0, [x0, #0xd50]
257ea10: bl       #0x237e174
257ea14: ldr      w8, [x0, #0xe0]
257ea18: cbnz     w8, #0x257ea20
257ea1c: bl       #0x237e260
257ea20: adrp     x0, #0xc612000
257ea24: ldr      x0, [x0, #0x2f8]
257ea28: bl       #0x237e174
257ea2c: mov      x1, x21
257ea30: mov      x2, x20
257ea34: mov      x3, xzr
257ea38: bl       #0x95261d0 ; -> Torappu.HGString.Format
257ea3c: b        #0x257ea70
257ea40: adrp     x0, #0xc6f1000
257ea44: ldr      x0, [x0, #0xd50]
257ea48: bl       #0x237e174
257ea4c: ldr      w8, [x0, #0xe0]
257ea50: cbnz     w8, #0x257ea58
257ea54: bl       #0x237e260
257ea58: adrp     x0, #0xc6d2000
257ea5c: ldr      x0, [x0, #0x1f0]
257ea60: bl       #0x237e174
257ea64: mov      x1, x21
257ea68: mov      x2, xzr
257ea6c: bl       #0x9525bf0 ; -> Torappu.HGString.Format
257ea70: mov      x20, x0
257ea74: adrp     x0, #0xc6d3000
257ea78: ldr      x0, [x0, #0x370]
257ea7c: bl       #0x237e174
257ea80: ldr      w8, [x0, #0xe0]
257ea84: cbnz     w8, #0x257ea8c
257ea88: bl       #0x237e260
257ea8c: mov      x0, x20
257ea90: mov      x1, xzr
257ea94: bl       #0x94f7720 ; -> UnityEngine.DLog.LogError
257ea98: b        #0x257e910
257ea9c: bl       #0x237e284
257eaa0: mov      w0, #8
257eaa4: bl       #0x1d4cb20
257eaa8: ldr      x8, [x21]
257eaac: str      x8, [x0]
257eab0: adrp     x1, #0xc09c000
257eab4: add      x1, x1, #0x710
257eab8: mov      x2, xzr
257eabc: bl       #0x1d4b400
257eac0: mov      x21, x0
257eac4: bl       #0x1d4cd30
257eac8: mov      x0, x21
257eacc: bl       #0x1d4ccd0
257ead0: bl       #0x1d4e528