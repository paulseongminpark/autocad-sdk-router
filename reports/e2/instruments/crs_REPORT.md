# CRS 픽셀↔핸들 역투영 브리지 보고서

## 판정

- 빌드 상태: **PASS**
- 합성 exact handle 회수: **4/4, recall 1.0, precision 1.0, F1 1.0**
- 독립 scalar oracle 대비 sparse relation: **MAPACC 1.0, CRS error 0.0**
- 겹친 핸들: **multi-hit 보존 PASS** (동일 위치의 두 핸들, collision pixel 74개)
- viewBox 축척 추정 selftest: **PASS**
- 퇴화 입력 selftest: **7/7 PASS**
- CubiCasa label-free 정합 smoke: **3/3 PASS**

이 PASS는 계측기와 좌표 브리지의 단위 자격 판정이다. 벽 탐지 모델의 성능 증거나 native-DWG handle truth 판정은 아니다.

## 구현 산출

`crs_bridge.py`는 stdlib, NumPy, Pillow만 사용하며 다음 계약을 구현한다.

1. `AffineTransform`
   - 명시된 `scale_x`, `scale_y`, `offset_x`, `offset_y`로 exact source→pixel affine을 만든다.
   - 미상 CRS의 제한적 fallback으로 `image_size / SVG viewBox` 축별 비율을 추정한다.
   - 정방향, 역행렬, point round-trip error와 transform provenance를 제공한다.
2. `RasterHandleBridge`
   - SEG-IR 선분을 핸들별로 독립 래스터화해 `A[p,h]` fractional coverage를 만든다.
   - 겹친 선분도 단일 winner로 줄이지 않고 같은 pixel에 여러 `(handle, coverage)` tuple을 보존한다.
   - mask, half-open box, polygon을 handle score로 역투영한다.
   - handle을 mask, pixel polyline, pixel box로 정방향 투영한다.
   - canvas 밖으로 완전히 잘린 handle은 `raster_missing=true`, `score=null`로 반환한다.
3. CubiCasa adapter
   - `cubicasa_ir.py`와 같은 polygon/polyline/line 및 SVG transform subset을 읽는다.
   - 핸들 순서와 이름은 converter의 `e{element}_s{edge}` 계약과 동일하다.
   - class token이나 Wall label은 정합 smoke에서 읽거나 사용하지 않는다.

픽셀 convention은 `array[y,x]`의 중심이 `(x+0.5,y+0.5)`인 것으로 고정했다. box는 `[x0,x1) × [y0,y1)`의 half-open 범위다. source/SVG coordinate에서 pixel-edge coordinate로 가는 matrix를 저장한다.

## 역투영 점수와 실패 분해

mask `Q[p]`와 sparse provenance `A[p,h]`에 대해 구현 점수는 다음 coverage 평균이다.

```text
s[h] = sum_p A[p,h] * Q[p] / sum_p A[p,h]
```

threshold 이상인 기존 handle만 선택한다. geometry나 handle을 생성·수정·병합하지 않는다. exact 회수가 1.0 미만이면 결과에 다음 원인을 항상 분리한다.

- 경계 픽셀: support가 canvas 경계에 닿거나 완전히 clipping된 handle
- 겹침: multi-hit collision pixel 수와 관련 handle
- 스케일 오차: 기대 affine과 실제 affine의 최대 matrix delta

합성 PASS에서도 이 필드는 생략하지 않았다. 이번 exact 결과에서는 경계 및 스케일 implicated handle이 0개였고, 겹침 자체는 74 pixel에서 관찰됐지만 정보가 보존되어 실패 원인은 아니었다.

## 독립 exact 검증 설계

production support는 NumPy vectorized point-to-segment distance로 계산한다. selftest oracle은 별도 scalar loop와 별도 거리 함수를 사용한다. oracle의 binary wall mask를 production bridge에 넣어 원 handle을 역투영하고, 두 구현의 `(row, col, handle, quantized coverage)` relation Jaccard를 MAPACC로 계산한다.

합성 scene은 수평선, 대각선, 비선택 hard negative, 완전히 겹친 두 handle, 비등방 scale, offset을 포함한다. 동일 위치 handle 두 개를 모두 truth에 넣어 단일-ID winner가 collision을 숨길 수 없게 했다.

## `--selftest` 실행 전문

명령:

```text
python D:\runs\e2_program\build\crs\crs_bridge.py --selftest
```

종료 코드: `0`

```json
{
  "pixel_center_convention": "array[y,x] center is (x+0.5,y+0.5)",
  "schema": "e2.crs_bridge.selftest.v1",
  "status": "PASS",
  "tests": [
    {
      "crs_error": 0.0,
      "failure_cause_decomposition": {
        "boundary_pixel": {
          "all_boundary_or_clipped_handles": [],
          "implicated_handles": []
        },
        "extra_handles": [],
        "missed_handles": [],
        "overlap": {
          "all_collision_handles": [
            "H_OVER_1",
            "H_OVER_2"
          ],
          "collision_pixels": 74,
          "implicated_handles": []
        },
        "scale_error": {
          "implicated": false,
          "max_abs_matrix_delta": 0.0
        }
      },
      "handle_recovery": {
        "f1": 1.0,
        "precision": 1.0,
        "recall": 1.0
      },
      "mapacc": 1.0,
      "multi_hit_overlap_preserved": true,
      "name": "synthetic_exact",
      "predicted_handles": [
        "H_A",
        "H_C",
        "H_OVER_1",
        "H_OVER_2"
      ],
      "roundtrip_max_error_source_units": 7.944109290391274e-15,
      "status": "PASS",
      "truth_handles": [
        "H_A",
        "H_C",
        "H_OVER_1",
        "H_OVER_2"
      ]
    },
    {
      "estimated_transform": {
        "matrix": [
          [
            2.5,
            0.0,
            -25.0
          ],
          [
            0.0,
            1.5,
            -30.0
          ],
          [
            0.0,
            0.0,
            1.0
          ]
        ],
        "pixel_center_convention": "array[y,x] center is (x+0.5,y+0.5)",
        "provenance": "estimated_image_size_vs_svg_viewBox"
      },
      "image_size": [
        300,
        120
      ],
      "max_abs_expected_matrix_delta": 0.0,
      "name": "viewbox_scale_estimate",
      "recovered_handles": [
        "EST_A",
        "EST_B"
      ],
      "scale_anisotropy_fraction": 0.4,
      "status": "PASS",
      "viewbox": [
        10.0,
        20.0,
        120.0,
        80.0
      ]
    },
    {
      "cases": [
        {
          "message": "degenerate SVG viewBox: (0, 0, 0, 10)",
          "name": "zero_width_viewbox",
          "observed": "ValueError",
          "status": "PASS"
        },
        {
          "message": "affine matrix is singular",
          "name": "singular_affine",
          "observed": "ValueError",
          "status": "PASS"
        },
        {
          "message": "zero-length segment is not bridgeable: ZERO",
          "name": "zero_length_segment",
          "observed": "ValueError",
          "status": "PASS"
        },
        {
          "message": "polygon must have shape (N>=3,2)",
          "name": "invalid_polygon",
          "observed": "ValueError",
          "status": "PASS"
        },
        {
          "message": "'unknown handle: MISSING'",
          "name": "unknown_handle",
          "observed": "KeyError",
          "status": "PASS"
        },
        {
          "match": {
            "handle": "OUTSIDE",
            "raster_missing": true,
            "score": null,
            "selected": false,
            "selected_coverage": 0.0,
            "support_coverage": 0.0,
            "support_pixels": 0,
            "touches_canvas_boundary": false
          },
          "name": "fully_clipped_segment",
          "status": "PASS"
        },
        {
          "name": "empty_mask",
          "selected_handles": [],
          "status": "PASS"
        }
      ],
      "name": "degenerate_cases",
      "status": "PASS"
    }
  ]
}
```

## CubiCasa 실데이터 smoke

명령:

```text
python D:\runs\e2_program\build\crs\crs_bridge.py --smoke
```

종료 코드: `0`, 전체 상태 `PASS`.

정합 측정에는 `F1_scaled.png` grayscale gradient edge와 class-neutral SVG segment sample만 사용했다. Wall mask, SVG class token, truth JSON은 사용하지 않았다. 각 SVG segment 위 점에서 반경 12 px 안의 가장 가까운 raw raster edge까지 거리를 측정했다.

| sample | F1_scaled 크기 | SVG viewBox 크기 | identity edge RMSE / median / p95 px | 12 px 내 일치 | full-image ratio RMSE px | ratio `sx, sy` | aspect mismatch |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10052 | 1549×1162 | 1500.940×855.100 | 1.889 / 0 / 5.000 | 99.409% | 10.922 | 1.0320, 1.3589 | 24.055% |
| 10062 | 1165×1165 | 1032.289×1079.250 | 2.574 / 0 / 6.000 | 98.214% | 8.578 | 1.1286, 1.0795 | 4.549% |
| 10106 | 2730×2002 | 2637.965×1894.740 | 2.613 / 0 / 6.325 | 98.118% | 8.728 | 1.0349, 1.0566 | 2.056% |

세 sample 모두 SVG coordinate를 F1_scaled pixel coordinate로 그대로 쓰는 identity mapping이 실측상 맞았다. median error가 모두 0 px이고 98.1% 이상이 12 px 안에서 raster edge를 찾았다. 남은 RMSE는 SVG에서 지원하지만 converter가 다루지 않는 path/rect/text, visibility/style 차이, stroke 폭, anti-aliasing의 영향이 섞인 label-free 진단 오차다.

반면 `image_size / viewBox`로 SVG extent를 PNG 전체에 강제 stretch한 fallback은 모두 edge audit에서 거부됐다. 특히 10052는 PNG 아래의 title/footer 및 바깥 margin 때문에 viewBox와 full image aspect가 24.055% 다르다. 따라서 dimension ratio fallback은 구현되어 있지만, 이 세 CubiCasa sample에는 쓰면 안 된다. 명시 transform이 없을 때는 추정 provenance를 보존하고 raw-edge audit나 외부 render manifest로 확인해야 한다.

estimated transform의 네 viewBox corner round-trip 최대 오차는 sample별 `1.14e-13`, `2.27e-13`, `5.08e-13` source unit이었다. 이는 affine 수치 역변환 오차이며 실제 이미지 정합 오차와는 별도다.

## converter 및 API 호환 확인

원본 `cubicasa_ir.py`를 read-only로 호출해 동일 세 sample에서 bridge SVG loader와 비교했다.

| sample | bridge segment | converter segment | handle 순서/이름 | converter의 0.001 반올림 좌표 대비 최대 차이 |
|---|---:|---:|---|---:|
| 10052 | 617 | 617 | 동일 | 0.0005 px |
| 10062 | 442 | 442 | 동일 | 0.0005 px |
| 10106 | 1783 | 1783 | 동일 | 0.0005 px |

별도 작은 fixture에서 동일 handle `A`가 mask→handle, box→handle, polygon→handle 세 경로 모두 정확히 회수됐고 handle→box는 `[1.0, 4.0, 13.0, 6.0]`으로 반환됐다.

## CLI 사용

Selftest와 smoke 외에 파일 기반 mapping mode가 있다.

```text
# known CRS: mask -> handles
python crs_bridge.py --seg-ir drawing.segir.json --image render.png \
  --mask predicted.png --scale-x 0.5 --scale-y 0.5 --offset-x 12 --offset-y 8

# unknown CRS fallback: SVG viewBox/image-size estimate, polygon -> handles
python crs_bridge.py --svg model.svg --image render.png \
  --polygon "[[10,10],[100,10],[100,80],[10,80]]"

# handles -> mask/boxes/polylines
python crs_bridge.py --seg-ir drawing.segir.json --svg model.svg --image render.png \
  --handles e1_s0 e1_s1 --output-mask handles.png
```

`--svg`가 있을 때도 class label은 mapping score에 들어가지 않는다. `--seg-ir` geometry가 있고 scale을 모르면 viewBox를 얻기 위한 `--svg`를 함께 줘야 한다.

## 미해결 및 한계

- image size와 viewBox 숫자만으로 crop, padding, letterbox를 식별할 수 없다. fallback transform은 추정 provenance를 명시하며, 실제 CubiCasa 세 건에서는 raw-edge audit가 이를 거부했다.
- SEG-IR converter와 동일하게 polygon/polyline/line edge만 handle universe로 삼는다. SVG path, rect, curve, fill 내부는 이 converter 계약의 segment handle이 아니므로 새 handle로 만들지 않았다.
- coverage는 segment 중심선과 설정된 pixel line width의 capsule support다. 벽 영역 polygon fill을 새 vector geometry로 바꾸지 않는다.
- `support()`와 역투영은 handle별 sparse/local 계산이지만, 모든 pixel collision을 한 dict로 물질화하는 `provenance()`는 매우 큰 drawing에서 메모리를 쓸 수 있다. 대규모 운영에서는 tile/stream serialization이 필요하다.
- raw-edge smoke는 alignment 진단이지 handle truth 평가가 아니다. real wall mask 없이 수행하라는 패킷 경계를 지켰으므로 CubiCasa wall handle recall을 주장하지 않는다.

BUILD_COMPLETE: crs
