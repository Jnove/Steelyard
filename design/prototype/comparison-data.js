window.COMPARISON_DATA = {
  "fixture_id": "14bf38e38385b866f3f64f253e2479c423adfcea88ee64f6e20139f8e58c9be6",
  "project": {
    "id": 1,
    "name": "杭州钱塘 · 保障性租赁住房 · 虚构示例项目",
    "params": {
      "site_area": 18000,
      "far_max": 2.5,
      "density_max": 0.28,
      "height_max": 54,
      "climate_zone": "夏热冬冷"
    },
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  },
  "evaluation": [
    {
      "scheme_id": "1",
      "scheme_name": "A 高品质",
      "compliance": [
        {
          "rule_id": "C-01",
          "name": "【示例】住宅层高下限",
          "status": "passed",
          "severity": "error",
          "value": 3.3,
          "limit": ">= 3.0",
          "formula": "floor_height >= 3.0",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】住宅层高下限 通过"
        },
        {
          "rule_id": "C-02",
          "name": "【示例】容积率不超地块上限",
          "status": "passed",
          "severity": "error",
          "value": null,
          "limit": null,
          "formula": "far <= far_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】容积率不超地块上限 通过"
        },
        {
          "rule_id": "C-03",
          "name": "【示例】建筑总高不超限高",
          "status": "passed",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "height <= height_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】建筑总高不超限高 通过"
        },
        {
          "rule_id": "S-02",
          "name": "【示例】钢结构方案需人工复核防火（条件硬约束）",
          "status": "not_applicable",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "risk_features contains '超限构件'",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "本方案不适用该规则（适用条件：structure_type == '钢结构'）"
        }
      ],
      "metrics": {
        "K-01": {
          "rule_id": "K-01",
          "name": "【示例】标准层重复率（越大越好）",
          "status": "scored",
          "value": 0.65,
          "score": 35,
          "dimension": "construction",
          "weight_in_dimension": 2,
          "formula": "std_floor_repeat；分段线性 0.5→0, 0.8→70, 0.95→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "K-02": {
          "rule_id": "K-02",
          "name": "【示例】预制构件种类数（越少越好）",
          "status": "scored",
          "value": 20,
          "score": 60,
          "dimension": "construction",
          "weight_in_dimension": 1,
          "formula": "component_types；分段线性 8→100, 20→60, 40→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-01": {
          "rule_id": "G-01",
          "name": "【示例】体形系数（越小越好）",
          "status": "scored",
          "value": 0.11837121212121213,
          "score": 100,
          "dimension": "green",
          "weight_in_dimension": 2,
          "formula": "shape_coef = envelope_area / volume；分段线性 0.2→100, 0.35→70, 0.6→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-02": {
          "rule_id": "G-02",
          "name": "【示例】预估装配率（越大越好）",
          "status": "scored",
          "value": 0.25,
          "score": 11.666666666666664,
          "dimension": "green",
          "weight_in_dimension": 1,
          "formula": "prefab_ratio_est；分段线性 0.2→0, 0.5→70, 0.8→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-01": {
          "rule_id": "Q-01",
          "name": "【示例】主要房间南向比例（适中最好）",
          "status": "scored",
          "value": 0.85,
          "score": 14.285714285714306,
          "dimension": "quality",
          "weight_in_dimension": 2,
          "formula": "south_room_ratio；分段线性 0.2→0, 0.55→100, 0.9→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-02": {
          "rule_id": "Q-02",
          "name": "【示例】得房率（越大越好）",
          "status": "scored",
          "value": 0.82,
          "score": 81.99999999999999,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "inner_area_ratio；分段线性 0.65→0, 0.78→70, 0.88→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-03": {
          "rule_id": "Q-03",
          "name": "【示例】单栋户数（越小越好，仅高层适用）",
          "status": "scored",
          "value": 80,
          "score": 90,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "units_per_building = units / buildings；分段线性 60→100, 120→70, 200→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "S-01": {
          "rule_id": "S-01",
          "name": "【示例】风险特征数量（越少越好）",
          "status": "scored",
          "value": 2,
          "score": 70,
          "dimension": "structure",
          "weight_in_dimension": 1,
          "formula": "len(risk_features)；分段线性 0→100, 2→70, 5→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        }
      },
      "dimension_scores": {
        "quality": 50.1429,
        "structure": 70,
        "construction": 43.3333,
        "green": 70.5556
      },
      "dimension_coverage": {
        "quality": 1,
        "structure": 1,
        "construction": 1,
        "green": 1
      },
      "topsis": null
    },
    {
      "scheme_id": "2",
      "scheme_name": "B 不合规",
      "compliance": [
        {
          "rule_id": "C-01",
          "name": "【示例】住宅层高下限",
          "status": "failed",
          "severity": "error",
          "value": 2.9,
          "limit": ">= 3.0",
          "formula": "floor_height >= 3.0",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "层高 2.9 m 低于示例阈值 3.0 m"
        },
        {
          "rule_id": "C-02",
          "name": "【示例】容积率不超地块上限",
          "status": "passed",
          "severity": "error",
          "value": null,
          "limit": null,
          "formula": "far <= far_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】容积率不超地块上限 通过"
        },
        {
          "rule_id": "C-03",
          "name": "【示例】建筑总高不超限高",
          "status": "passed",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "height <= height_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】建筑总高不超限高 通过"
        },
        {
          "rule_id": "S-02",
          "name": "【示例】钢结构方案需人工复核防火（条件硬约束）",
          "status": "not_applicable",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "risk_features contains '超限构件'",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "本方案不适用该规则（适用条件：structure_type == '钢结构'）"
        }
      ],
      "metrics": {
        "K-01": {
          "rule_id": "K-01",
          "name": "【示例】标准层重复率（越大越好）",
          "status": "scored",
          "value": 0.8,
          "score": 70,
          "dimension": "construction",
          "weight_in_dimension": 2,
          "formula": "std_floor_repeat；分段线性 0.5→0, 0.8→70, 0.95→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "K-02": {
          "rule_id": "K-02",
          "name": "【示例】预制构件种类数（越少越好）",
          "status": "scored",
          "value": 14,
          "score": 80,
          "dimension": "construction",
          "weight_in_dimension": 1,
          "formula": "component_types；分段线性 8→100, 20→60, 40→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-01": {
          "rule_id": "G-01",
          "name": "【示例】体形系数（越小越好）",
          "status": "scored",
          "value": 0.11156186612576065,
          "score": 100,
          "dimension": "green",
          "weight_in_dimension": 2,
          "formula": "shape_coef = envelope_area / volume；分段线性 0.2→100, 0.35→70, 0.6→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-02": {
          "rule_id": "G-02",
          "name": "【示例】预估装配率（越大越好）",
          "status": "scored",
          "value": 0.45,
          "score": 58.333333333333336,
          "dimension": "green",
          "weight_in_dimension": 1,
          "formula": "prefab_ratio_est；分段线性 0.2→0, 0.5→70, 0.8→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-01": {
          "rule_id": "Q-01",
          "name": "【示例】主要房间南向比例（适中最好）",
          "status": "scored",
          "value": 0.7,
          "score": 57.14285714285717,
          "dimension": "quality",
          "weight_in_dimension": 2,
          "formula": "south_room_ratio；分段线性 0.2→0, 0.55→100, 0.9→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-02": {
          "rule_id": "Q-02",
          "name": "【示例】得房率（越大越好）",
          "status": "scored",
          "value": 0.74,
          "score": 48.461538461538446,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "inner_area_ratio；分段线性 0.65→0, 0.78→70, 0.88→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-03": {
          "rule_id": "Q-03",
          "name": "【示例】单栋户数（越小越好，仅高层适用）",
          "status": "scored",
          "value": 85,
          "score": 87.5,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "units_per_building = units / buildings；分段线性 60→100, 120→70, 200→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "S-01": {
          "rule_id": "S-01",
          "name": "【示例】风险特征数量（越少越好）",
          "status": "scored",
          "value": 0,
          "score": 100,
          "dimension": "structure",
          "weight_in_dimension": 1,
          "formula": "len(risk_features)；分段线性 0→100, 2→70, 5→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        }
      },
      "dimension_scores": {
        "quality": 62.5618,
        "structure": 100,
        "construction": 73.3333,
        "green": 86.1111
      },
      "dimension_coverage": {
        "quality": 1,
        "structure": 1,
        "construction": 1,
        "green": 1
      },
      "topsis": null
    },
    {
      "scheme_id": "3",
      "scheme_name": "C MiC 高标准化",
      "compliance": [
        {
          "rule_id": "C-01",
          "name": "【示例】住宅层高下限",
          "status": "passed",
          "severity": "error",
          "value": 3,
          "limit": ">= 3.0",
          "formula": "floor_height >= 3.0",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】住宅层高下限 通过"
        },
        {
          "rule_id": "C-02",
          "name": "【示例】容积率不超地块上限",
          "status": "passed",
          "severity": "error",
          "value": null,
          "limit": null,
          "formula": "far <= far_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】容积率不超地块上限 通过"
        },
        {
          "rule_id": "C-03",
          "name": "【示例】建筑总高不超限高",
          "status": "passed",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "height <= height_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】建筑总高不超限高 通过"
        },
        {
          "rule_id": "S-02",
          "name": "【示例】钢结构方案需人工复核防火（条件硬约束）",
          "status": "not_applicable",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "risk_features contains '超限构件'",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "本方案不适用该规则（适用条件：structure_type == '钢结构'）"
        }
      ],
      "metrics": {
        "K-01": {
          "rule_id": "K-01",
          "name": "【示例】标准层重复率（越大越好）",
          "status": "scored",
          "value": 0.95,
          "score": 100,
          "dimension": "construction",
          "weight_in_dimension": 2,
          "formula": "std_floor_repeat；分段线性 0.5→0, 0.8→70, 0.95→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "K-02": {
          "rule_id": "K-02",
          "name": "【示例】预制构件种类数（越少越好）",
          "status": "scored",
          "value": 8,
          "score": 100,
          "dimension": "construction",
          "weight_in_dimension": 1,
          "formula": "component_types；分段线性 8→100, 20→60, 40→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-01": {
          "rule_id": "G-01",
          "name": "【示例】体形系数（越小越好）",
          "status": "scored",
          "value": 0.1111111111111111,
          "score": 100,
          "dimension": "green",
          "weight_in_dimension": 2,
          "formula": "shape_coef = envelope_area / volume；分段线性 0.2→100, 0.35→70, 0.6→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-02": {
          "rule_id": "G-02",
          "name": "【示例】预估装配率（越大越好）",
          "status": "scored",
          "value": 0.75,
          "score": 95,
          "dimension": "green",
          "weight_in_dimension": 1,
          "formula": "prefab_ratio_est；分段线性 0.2→0, 0.5→70, 0.8→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-01": {
          "rule_id": "Q-01",
          "name": "【示例】主要房间南向比例（适中最好）",
          "status": "scored",
          "value": 0.72,
          "score": 51.428571428571445,
          "dimension": "quality",
          "weight_in_dimension": 2,
          "formula": "south_room_ratio；分段线性 0.2→0, 0.55→100, 0.9→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-02": {
          "rule_id": "Q-02",
          "name": "【示例】得房率（越大越好）",
          "status": "scored",
          "value": 0.76,
          "score": 59.23076923076922,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "inner_area_ratio；分段线性 0.65→0, 0.78→70, 0.88→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-03": {
          "rule_id": "Q-03",
          "name": "【示例】单栋户数（越小越好，仅高层适用）",
          "status": "scored",
          "value": 108,
          "score": 76,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "units_per_building = units / buildings；分段线性 60→100, 120→70, 200→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "S-01": {
          "rule_id": "S-01",
          "name": "【示例】风险特征数量（越少越好）",
          "status": "scored",
          "value": 0,
          "score": 100,
          "dimension": "structure",
          "weight_in_dimension": 1,
          "formula": "len(risk_features)；分段线性 0→100, 2→70, 5→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        }
      },
      "dimension_scores": {
        "quality": 59.522,
        "structure": 100,
        "construction": 100,
        "green": 98.3333
      },
      "dimension_coverage": {
        "quality": 1,
        "structure": 1,
        "construction": 1,
        "green": 1
      },
      "topsis": null
    },
    {
      "scheme_id": "4",
      "scheme_name": "D 均衡",
      "compliance": [
        {
          "rule_id": "C-01",
          "name": "【示例】住宅层高下限",
          "status": "passed",
          "severity": "error",
          "value": 3,
          "limit": ">= 3.0",
          "formula": "floor_height >= 3.0",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】住宅层高下限 通过"
        },
        {
          "rule_id": "C-02",
          "name": "【示例】容积率不超地块上限",
          "status": "passed",
          "severity": "error",
          "value": null,
          "limit": null,
          "formula": "far <= far_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】容积率不超地块上限 通过"
        },
        {
          "rule_id": "C-03",
          "name": "【示例】建筑总高不超限高",
          "status": "passed",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "height <= height_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】建筑总高不超限高 通过"
        },
        {
          "rule_id": "S-02",
          "name": "【示例】钢结构方案需人工复核防火（条件硬约束）",
          "status": "not_applicable",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "risk_features contains '超限构件'",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "本方案不适用该规则（适用条件：structure_type == '钢结构'）"
        }
      ],
      "metrics": {
        "K-01": {
          "rule_id": "K-01",
          "name": "【示例】标准层重复率（越大越好）",
          "status": "scored",
          "value": 0.85,
          "score": 80,
          "dimension": "construction",
          "weight_in_dimension": 2,
          "formula": "std_floor_repeat；分段线性 0.5→0, 0.8→70, 0.95→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "K-02": {
          "rule_id": "K-02",
          "name": "【示例】预制构件种类数（越少越好）",
          "status": "scored",
          "value": 12,
          "score": 86.66666666666667,
          "dimension": "construction",
          "weight_in_dimension": 1,
          "formula": "component_types；分段线性 8→100, 20→60, 40→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-01": {
          "rule_id": "G-01",
          "name": "【示例】体形系数（越小越好）",
          "status": "scored",
          "value": 0.10620915032679738,
          "score": 100,
          "dimension": "green",
          "weight_in_dimension": 2,
          "formula": "shape_coef = envelope_area / volume；分段线性 0.2→100, 0.35→70, 0.6→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-02": {
          "rule_id": "G-02",
          "name": "【示例】预估装配率（越大越好）",
          "status": "scored",
          "value": 0.5,
          "score": 70,
          "dimension": "green",
          "weight_in_dimension": 1,
          "formula": "prefab_ratio_est；分段线性 0.2→0, 0.5→70, 0.8→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-01": {
          "rule_id": "Q-01",
          "name": "【示例】主要房间南向比例（适中最好）",
          "status": "scored",
          "value": 0.78,
          "score": 34.28571428571429,
          "dimension": "quality",
          "weight_in_dimension": 2,
          "formula": "south_room_ratio；分段线性 0.2→0, 0.55→100, 0.9→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-02": {
          "rule_id": "Q-02",
          "name": "【示例】得房率（越大越好）",
          "status": "scored",
          "value": 0.78,
          "score": 70,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "inner_area_ratio；分段线性 0.65→0, 0.78→70, 0.88→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-03": {
          "rule_id": "Q-03",
          "name": "【示例】单栋户数（越小越好，仅高层适用）",
          "status": "scored",
          "value": 102,
          "score": 79,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "units_per_building = units / buildings；分段线性 60→100, 120→70, 200→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "S-01": {
          "rule_id": "S-01",
          "name": "【示例】风险特征数量（越少越好）",
          "status": "scored",
          "value": 0,
          "score": 100,
          "dimension": "structure",
          "weight_in_dimension": 1,
          "formula": "len(risk_features)；分段线性 0→100, 2→70, 5→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        }
      },
      "dimension_scores": {
        "quality": 54.3929,
        "structure": 100,
        "construction": 82.2222,
        "green": 90
      },
      "dimension_coverage": {
        "quality": 1,
        "structure": 1,
        "construction": 1,
        "green": 1
      },
      "topsis": null
    },
    {
      "scheme_id": "5",
      "scheme_name": "E 被支配",
      "compliance": [
        {
          "rule_id": "C-01",
          "name": "【示例】住宅层高下限",
          "status": "passed",
          "severity": "error",
          "value": 3,
          "limit": ">= 3.0",
          "formula": "floor_height >= 3.0",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】住宅层高下限 通过"
        },
        {
          "rule_id": "C-02",
          "name": "【示例】容积率不超地块上限",
          "status": "passed",
          "severity": "error",
          "value": null,
          "limit": null,
          "formula": "far <= far_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】容积率不超地块上限 通过"
        },
        {
          "rule_id": "C-03",
          "name": "【示例】建筑总高不超限高",
          "status": "passed",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "height <= height_max",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "【示例】建筑总高不超限高 通过"
        },
        {
          "rule_id": "S-02",
          "name": "【示例】钢结构方案需人工复核防火（条件硬约束）",
          "status": "not_applicable",
          "severity": "warning",
          "value": null,
          "limit": null,
          "formula": "risk_features contains '超限构件'",
          "source": "TODO(专业组)：示例数值，正式条文号待补",
          "missing_fields": [],
          "message": "本方案不适用该规则（适用条件：structure_type == '钢结构'）"
        }
      ],
      "metrics": {
        "K-01": {
          "rule_id": "K-01",
          "name": "【示例】标准层重复率（越大越好）",
          "status": "scored",
          "value": 0.75,
          "score": 58.33333333333333,
          "dimension": "construction",
          "weight_in_dimension": 2,
          "formula": "std_floor_repeat；分段线性 0.5→0, 0.8→70, 0.95→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "K-02": {
          "rule_id": "K-02",
          "name": "【示例】预制构件种类数（越少越好）",
          "status": "scored",
          "value": 15,
          "score": 76.66666666666666,
          "dimension": "construction",
          "weight_in_dimension": 1,
          "formula": "component_types；分段线性 8→100, 20→60, 40→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-01": {
          "rule_id": "G-01",
          "name": "【示例】体形系数（越小越好）",
          "status": "scored",
          "value": 0.11437908496732026,
          "score": 100,
          "dimension": "green",
          "weight_in_dimension": 2,
          "formula": "shape_coef = envelope_area / volume；分段线性 0.2→100, 0.35→70, 0.6→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "G-02": {
          "rule_id": "G-02",
          "name": "【示例】预估装配率（越大越好）",
          "status": "scored",
          "value": 0.3,
          "score": 23.33333333333333,
          "dimension": "green",
          "weight_in_dimension": 1,
          "formula": "prefab_ratio_est；分段线性 0.2→0, 0.5→70, 0.8→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-01": {
          "rule_id": "Q-01",
          "name": "【示例】主要房间南向比例（适中最好）",
          "status": "scored",
          "value": 0.68,
          "score": 62.857142857142854,
          "dimension": "quality",
          "weight_in_dimension": 2,
          "formula": "south_room_ratio；分段线性 0.2→0, 0.55→100, 0.9→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-02": {
          "rule_id": "Q-02",
          "name": "【示例】得房率（越大越好）",
          "status": "scored",
          "value": 0.72,
          "score": 37.692307692307665,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "inner_area_ratio；分段线性 0.65→0, 0.78→70, 0.88→100",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "Q-03": {
          "rule_id": "Q-03",
          "name": "【示例】单栋户数（越小越好，仅高层适用）",
          "status": "scored",
          "value": 102,
          "score": 79,
          "dimension": "quality",
          "weight_in_dimension": 1,
          "formula": "units_per_building = units / buildings；分段线性 60→100, 120→70, 200→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        },
        "S-01": {
          "rule_id": "S-01",
          "name": "【示例】风险特征数量（越少越好）",
          "status": "scored",
          "value": 2,
          "score": 70,
          "dimension": "structure",
          "weight_in_dimension": 1,
          "formula": "len(risk_features)；分段线性 0→100, 2→70, 5→0",
          "source": "TODO(专业组)：示例数值，正式依据待补",
          "missing_fields": []
        }
      },
      "dimension_scores": {
        "quality": 60.6016,
        "structure": 70,
        "construction": 64.4444,
        "green": 74.4444
      },
      "dimension_coverage": {
        "quality": 1,
        "structure": 1,
        "construction": 1,
        "green": 1
      },
      "topsis": null
    }
  ],
  "rules": [
    {
      "id": "C-01",
      "name": "【示例】住宅层高下限",
      "type": "hard",
      "source": "TODO(专业组)：示例数值，正式条文号待补",
      "when": null,
      "check": "floor_height >= 3.0",
      "message": "层高 {floor_height} m 低于示例阈值 3.0 m",
      "severity": "error",
      "dimension": null,
      "value": null,
      "scoring": null,
      "weight_in_dimension": 1
    },
    {
      "id": "C-02",
      "name": "【示例】容积率不超地块上限",
      "type": "hard",
      "source": "TODO(专业组)：示例数值，正式条文号待补",
      "when": null,
      "check": "far <= far_max",
      "message": "容积率 {far} 超过地块上限 {far_max}",
      "severity": "error",
      "dimension": null,
      "value": null,
      "scoring": null,
      "weight_in_dimension": 1
    },
    {
      "id": "C-03",
      "name": "【示例】建筑总高不超限高",
      "type": "hard",
      "source": "TODO(专业组)：示例数值，正式条文号待补",
      "when": null,
      "check": "height <= height_max",
      "message": "建筑总高 {height} m 超过限高 {height_max} m",
      "severity": "warning",
      "dimension": null,
      "value": null,
      "scoring": null,
      "weight_in_dimension": 1
    },
    {
      "id": "K-01",
      "name": "【示例】标准层重复率（越大越好）",
      "type": "metric",
      "source": "TODO(专业组)：示例数值，正式依据待补",
      "when": null,
      "check": null,
      "message": null,
      "severity": "error",
      "dimension": "construction",
      "value": "std_floor_repeat",
      "scoring": {
        "kind": "piecewise",
        "points": [
          [
            0.5,
            0
          ],
          [
            0.8,
            70
          ],
          [
            0.95,
            100
          ]
        ]
      },
      "weight_in_dimension": 2
    },
    {
      "id": "K-02",
      "name": "【示例】预制构件种类数（越少越好）",
      "type": "metric",
      "source": "TODO(专业组)：示例数值，正式依据待补",
      "when": null,
      "check": null,
      "message": null,
      "severity": "error",
      "dimension": "construction",
      "value": "component_types",
      "scoring": {
        "kind": "piecewise",
        "points": [
          [
            8,
            100
          ],
          [
            20,
            60
          ],
          [
            40,
            0
          ]
        ]
      },
      "weight_in_dimension": 1
    },
    {
      "id": "G-01",
      "name": "【示例】体形系数（越小越好）",
      "type": "metric",
      "source": "TODO(专业组)：示例数值，正式依据待补",
      "when": null,
      "check": null,
      "message": null,
      "severity": "error",
      "dimension": "green",
      "value": "shape_coef",
      "scoring": {
        "kind": "piecewise",
        "points": [
          [
            0.2,
            100
          ],
          [
            0.35,
            70
          ],
          [
            0.6,
            0
          ]
        ]
      },
      "weight_in_dimension": 2
    },
    {
      "id": "G-02",
      "name": "【示例】预估装配率（越大越好）",
      "type": "metric",
      "source": "TODO(专业组)：示例数值，正式依据待补",
      "when": null,
      "check": null,
      "message": null,
      "severity": "error",
      "dimension": "green",
      "value": "prefab_ratio_est",
      "scoring": {
        "kind": "piecewise",
        "points": [
          [
            0.2,
            0
          ],
          [
            0.5,
            70
          ],
          [
            0.8,
            100
          ]
        ]
      },
      "weight_in_dimension": 1
    },
    {
      "id": "Q-01",
      "name": "【示例】主要房间南向比例（适中最好）",
      "type": "metric",
      "source": "TODO(专业组)：示例数值，正式依据待补",
      "when": null,
      "check": null,
      "message": null,
      "severity": "error",
      "dimension": "quality",
      "value": "south_room_ratio",
      "scoring": {
        "kind": "piecewise",
        "points": [
          [
            0.2,
            0
          ],
          [
            0.55,
            100
          ],
          [
            0.9,
            0
          ]
        ]
      },
      "weight_in_dimension": 2
    },
    {
      "id": "Q-02",
      "name": "【示例】得房率（越大越好）",
      "type": "metric",
      "source": "TODO(专业组)：示例数值，正式依据待补",
      "when": null,
      "check": null,
      "message": null,
      "severity": "error",
      "dimension": "quality",
      "value": "inner_area_ratio",
      "scoring": {
        "kind": "piecewise",
        "points": [
          [
            0.65,
            0
          ],
          [
            0.78,
            70
          ],
          [
            0.88,
            100
          ]
        ]
      },
      "weight_in_dimension": 1
    },
    {
      "id": "Q-03",
      "name": "【示例】单栋户数（越小越好，仅高层适用）",
      "type": "metric",
      "source": "TODO(专业组)：示例数值，正式依据待补",
      "when": "floors >= 7",
      "check": null,
      "message": null,
      "severity": "error",
      "dimension": "quality",
      "value": "units_per_building",
      "scoring": {
        "kind": "piecewise",
        "points": [
          [
            60,
            100
          ],
          [
            120,
            70
          ],
          [
            200,
            0
          ]
        ]
      },
      "weight_in_dimension": 1
    },
    {
      "id": "S-01",
      "name": "【示例】风险特征数量（越少越好）",
      "type": "metric",
      "source": "TODO(专业组)：示例数值，正式依据待补",
      "when": null,
      "check": null,
      "message": null,
      "severity": "error",
      "dimension": "structure",
      "value": "len(risk_features)",
      "scoring": {
        "kind": "piecewise",
        "points": [
          [
            0,
            100
          ],
          [
            2,
            70
          ],
          [
            5,
            0
          ]
        ]
      },
      "weight_in_dimension": 1
    },
    {
      "id": "S-02",
      "name": "【示例】钢结构方案需人工复核防火（条件硬约束）",
      "type": "hard",
      "source": "TODO(专业组)：示例数值，正式条文号待补",
      "when": "structure_type == '钢结构'",
      "check": "risk_features contains '超限构件'",
      "message": "钢结构方案请把需要人工复核的风险特征列入 risk_features",
      "severity": "warning",
      "dimension": null,
      "value": null,
      "scoring": null,
      "weight_in_dimension": 1
    }
  ],
  "schemes": [
    {
      "id": 1,
      "project_id": 1,
      "name": "A 高品质",
      "params": {
        "structure_type": "剪力墙",
        "units": 320,
        "unit_mix": {
          "三室": 160,
          "两室": 160
        },
        "floor_height": 3.3,
        "inner_area_ratio": 0.82,
        "south_room_ratio": 0.85,
        "window_floor_ratio": 0.28,
        "window_wall_ratio": {
          "南": 0.45,
          "北": 0.3,
          "东": 0.3,
          "西": 0.3
        },
        "elevators_per_unit": 2,
        "gfa": 38400,
        "footprint": 2400,
        "buildings": 4,
        "floors": 16,
        "envelope_area": 15000,
        "volume": 126720,
        "std_floor_repeat": 0.65,
        "component_types": 20,
        "risk_features": [
          "大悬挑",
          "高支模"
        ],
        "prefab_ratio_est": 0.25
      },
      "is_whatif": false,
      "parent_id": null,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    },
    {
      "id": 2,
      "project_id": 1,
      "name": "B 不合规",
      "params": {
        "structure_type": "剪力墙",
        "units": 340,
        "unit_mix": {
          "两室": 170,
          "三室": 170
        },
        "floor_height": 2.9,
        "inner_area_ratio": 0.74,
        "south_room_ratio": 0.7,
        "window_floor_ratio": 0.22,
        "window_wall_ratio": {
          "南": 0.4,
          "北": 0.25,
          "东": 0.25,
          "西": 0.25
        },
        "elevators_per_unit": 1,
        "gfa": 40800,
        "footprint": 2400,
        "buildings": 4,
        "floors": 17,
        "envelope_area": 13200,
        "volume": 118320,
        "std_floor_repeat": 0.8,
        "component_types": 14,
        "risk_features": [],
        "prefab_ratio_est": 0.45
      },
      "is_whatif": false,
      "parent_id": null,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    },
    {
      "id": 3,
      "project_id": 1,
      "name": "C MiC 高标准化",
      "params": {
        "structure_type": "MiC",
        "units": 432,
        "unit_mix": {
          "一室": 144,
          "两室": 192,
          "三室": 96
        },
        "floor_height": 3,
        "inner_area_ratio": 0.76,
        "south_room_ratio": 0.72,
        "window_floor_ratio": 0.22,
        "window_wall_ratio": {
          "南": 0.4,
          "北": 0.25,
          "东": 0.25,
          "西": 0.25
        },
        "elevators_per_unit": 2,
        "gfa": 43200,
        "footprint": 2400,
        "buildings": 4,
        "floors": 18,
        "envelope_area": 14400,
        "volume": 129600,
        "std_floor_repeat": 0.95,
        "component_types": 8,
        "risk_features": [],
        "prefab_ratio_est": 0.75
      },
      "is_whatif": false,
      "parent_id": null,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    },
    {
      "id": 4,
      "project_id": 1,
      "name": "D 均衡",
      "params": {
        "structure_type": "框架-剪力墙",
        "units": 408,
        "unit_mix": {
          "两室": 204,
          "三室": 204
        },
        "floor_height": 3,
        "inner_area_ratio": 0.78,
        "south_room_ratio": 0.78,
        "window_floor_ratio": 0.25,
        "window_wall_ratio": {
          "南": 0.42,
          "北": 0.27,
          "东": 0.27,
          "西": 0.27
        },
        "elevators_per_unit": 2,
        "gfa": 40800,
        "footprint": 2400,
        "buildings": 4,
        "floors": 17,
        "envelope_area": 13000,
        "volume": 122400,
        "std_floor_repeat": 0.85,
        "component_types": 12,
        "risk_features": [],
        "prefab_ratio_est": 0.5
      },
      "is_whatif": false,
      "parent_id": null,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    },
    {
      "id": 5,
      "project_id": 1,
      "name": "E 被支配",
      "params": {
        "structure_type": "框架",
        "units": 408,
        "unit_mix": {
          "两室": 204,
          "三室": 204
        },
        "floor_height": 3,
        "inner_area_ratio": 0.72,
        "south_room_ratio": 0.68,
        "window_floor_ratio": 0.2,
        "window_wall_ratio": {
          "南": 0.35,
          "北": 0.22,
          "东": 0.22,
          "西": 0.22
        },
        "elevators_per_unit": 1,
        "gfa": 40800,
        "footprint": 2400,
        "buildings": 4,
        "floors": 17,
        "envelope_area": 14000,
        "volume": 122400,
        "std_floor_repeat": 0.75,
        "component_types": 15,
        "risk_features": [
          "大悬挑",
          "复杂地质"
        ],
        "prefab_ratio_est": 0.3
      },
      "is_whatif": false,
      "parent_id": null,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    }
  ],
  "roles": {
    "government": {
      "label": "政府 / 保障房平台",
      "weights": [
        0.3636363636363637,
        0.1818181818181818,
        0.0909090909090909,
        0.3636363636363636
      ],
      "ranking": [
        {
          "scheme_id": "3",
          "scheme_name": "C MiC 高标准化",
          "dimension_scores": [
            59.522,
            100,
            100,
            98.3333
          ],
          "closeness": 0.9591198783082729,
          "rank": 1,
          "is_non_dominated": true,
          "dominated_by": [],
          "first_place_probability": 1
        },
        {
          "scheme_id": "4",
          "scheme_name": "D 均衡",
          "dimension_scores": [
            54.3929,
            100,
            82.2222,
            90
          ],
          "closeness": 0.6711369052059001,
          "rank": 2,
          "is_non_dominated": false,
          "dominated_by": [
            "3"
          ],
          "first_place_probability": 0
        },
        {
          "scheme_id": "5",
          "scheme_name": "E 被支配",
          "dimension_scores": [
            60.6016,
            70,
            64.4444,
            74.4444
          ],
          "closeness": 0.3658127997974247,
          "rank": 3,
          "is_non_dominated": true,
          "dominated_by": [],
          "first_place_probability": 0
        },
        {
          "scheme_id": "1",
          "scheme_name": "A 高品质",
          "dimension_scores": [
            50.1429,
            70,
            43.3333,
            70.5556
          ],
          "closeness": 0,
          "rank": 4,
          "is_non_dominated": false,
          "dominated_by": [
            "3",
            "4",
            "5"
          ],
          "first_place_probability": 0
        }
      ],
      "excluded": [
        {
          "scheme_id": "2",
          "scheme_name": "B 不合规",
          "reason": "有 1 条 error 级硬约束未通过（C-01），默认不参与排名；想让它参与请传 include_noncompliant=true",
          "failed_rules": [
            "C-01"
          ]
        }
      ]
    },
    "developer": {
      "label": "开发企业",
      "weights": [
        0.39073413710298166,
        0.1460987815076119,
        0.3669530333930548,
        0.09621404799635172
      ],
      "ranking": [
        {
          "scheme_id": "3",
          "scheme_name": "C MiC 高标准化",
          "dimension_scores": [
            59.522,
            100,
            100,
            98.3333
          ],
          "closeness": 0.9747660296976418,
          "rank": 1,
          "is_non_dominated": true,
          "dominated_by": [],
          "first_place_probability": 1
        },
        {
          "scheme_id": "4",
          "scheme_name": "D 均衡",
          "dimension_scores": [
            54.3929,
            100,
            82.2222,
            90
          ],
          "closeness": 0.6724526521908942,
          "rank": 2,
          "is_non_dominated": false,
          "dominated_by": [
            "3"
          ],
          "first_place_probability": 0
        },
        {
          "scheme_id": "5",
          "scheme_name": "E 被支配",
          "dimension_scores": [
            60.6016,
            70,
            64.4444,
            74.4444
          ],
          "closeness": 0.40835754791884565,
          "rank": 3,
          "is_non_dominated": true,
          "dominated_by": [],
          "first_place_probability": 0
        },
        {
          "scheme_id": "1",
          "scheme_name": "A 高品质",
          "dimension_scores": [
            50.1429,
            70,
            43.3333,
            70.5556
          ],
          "closeness": 0,
          "rank": 4,
          "is_non_dominated": false,
          "dominated_by": [
            "3",
            "4",
            "5"
          ],
          "first_place_probability": 0
        }
      ],
      "excluded": [
        {
          "scheme_id": "2",
          "scheme_name": "B 不合规",
          "reason": "有 1 条 error 级硬约束未通过（C-01），默认不参与排名；想让它参与请传 include_noncompliant=true",
          "failed_rules": [
            "C-01"
          ]
        }
      ]
    },
    "contractor": {
      "label": "施工总包",
      "weights": [
        0.12096271328944483,
        0.2196042290598375,
        0.5384703443612728,
        0.12096271328944473
      ],
      "ranking": [
        {
          "scheme_id": "3",
          "scheme_name": "C MiC 高标准化",
          "dimension_scores": [
            59.522,
            100,
            100,
            98.3333
          ],
          "closeness": 0.9944278883299199,
          "rank": 1,
          "is_non_dominated": true,
          "dominated_by": [],
          "first_place_probability": 1
        },
        {
          "scheme_id": "4",
          "scheme_name": "D 均衡",
          "dimension_scores": [
            54.3929,
            100,
            82.2222,
            90
          ],
          "closeness": 0.6930780760993225,
          "rank": 2,
          "is_non_dominated": false,
          "dominated_by": [
            "3"
          ],
          "first_place_probability": 0
        },
        {
          "scheme_id": "5",
          "scheme_name": "E 被支配",
          "dimension_scores": [
            60.6016,
            70,
            64.4444,
            74.4444
          ],
          "closeness": 0.3632437602774594,
          "rank": 3,
          "is_non_dominated": true,
          "dominated_by": [],
          "first_place_probability": 0
        },
        {
          "scheme_id": "1",
          "scheme_name": "A 高品质",
          "dimension_scores": [
            50.1429,
            70,
            43.3333,
            70.5556
          ],
          "closeness": 0,
          "rank": 4,
          "is_non_dominated": false,
          "dominated_by": [
            "3",
            "4",
            "5"
          ],
          "first_place_probability": 0
        }
      ],
      "excluded": [
        {
          "scheme_id": "2",
          "scheme_name": "B 不合规",
          "reason": "有 1 条 error 级硬约束未通过（C-01），默认不参与排名；想让它参与请传 include_noncompliant=true",
          "failed_rules": [
            "C-01"
          ]
        }
      ]
    },
    "resident": {
      "label": "住户",
      "weights": [
        0.4828856165547409,
        0.27197446132471886,
        0.08815006135763408,
        0.15698986076290622
      ],
      "ranking": [
        {
          "scheme_id": "3",
          "scheme_name": "C MiC 高标准化",
          "dimension_scores": [
            59.522,
            100,
            100,
            98.3333
          ],
          "closeness": 0.9418423233676215,
          "rank": 1,
          "is_non_dominated": true,
          "dominated_by": [],
          "first_place_probability": 1
        },
        {
          "scheme_id": "4",
          "scheme_name": "D 均衡",
          "dimension_scores": [
            54.3929,
            100,
            82.2222,
            90
          ],
          "closeness": 0.6635845902494694,
          "rank": 2,
          "is_non_dominated": false,
          "dominated_by": [
            "3"
          ],
          "first_place_probability": 0
        },
        {
          "scheme_id": "5",
          "scheme_name": "E 被支配",
          "dimension_scores": [
            60.6016,
            70,
            64.4444,
            74.4444
          ],
          "closeness": 0.4533752114741232,
          "rank": 3,
          "is_non_dominated": true,
          "dominated_by": [],
          "first_place_probability": 0
        },
        {
          "scheme_id": "1",
          "scheme_name": "A 高品质",
          "dimension_scores": [
            50.1429,
            70,
            43.3333,
            70.5556
          ],
          "closeness": 0,
          "rank": 4,
          "is_non_dominated": false,
          "dominated_by": [
            "3",
            "4",
            "5"
          ],
          "first_place_probability": 0
        }
      ],
      "excluded": [
        {
          "scheme_id": "2",
          "scheme_name": "B 不合规",
          "reason": "有 1 条 error 级硬约束未通过（C-01），默认不参与排名；想让它参与请传 include_noncompliant=true",
          "failed_rules": [
            "C-01"
          ]
        }
      ]
    }
  }
};
