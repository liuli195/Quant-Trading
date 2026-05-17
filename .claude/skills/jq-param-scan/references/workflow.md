# JQ Param Scan 娴佺▼

## 闃舵涓€锛氶厤缃敓鎴?

1. 浠庣敤鎴锋弿杩颁腑鎻愬彇锛氬弬鏁板悕銆佸€煎垪琛ㄦ垨鑼冨洿+姝ラ暱銆佺瓥鐣ユ枃浠惰矾寰勩€?
2. 鐢熸垚 `ScenarioConfig` sweep 閰嶇疆锛?
   - `sweep.strategy` = `"grid"`锛堝鍙傛暟姝ｄ氦锛夋垨 `"list"`锛堝崟鍙傛暟鏋氫妇锛?
   - `sweep.dimensions` 瀹氫箟鍙傛暟缁村害
3. 灏嗛厤缃啓鍏?`strategies/<strategy>/test_batches/<batch_id>/scenario.json`銆?

## 闃舵浜岋細璁″垝灞曠ず

璁＄畻骞跺睍绀猴細

- 鍙傛暟缁勫悎鏁?= 鍚勭淮搴︽按骞虫暟鐨勪箻绉?
- 棰勪及鍗曟鍥炴祴鑰楁椂锛堝熀浜庡巻鍙叉暟鎹及绠楋級
- 鎬昏€楁椂 = 缁勫悎鏁?脳 鍗曟鑰楁椂
- 褰撴棩鍓╀綑棰濆害
- 纭鎻愮ず锛歚--yes` 琛ㄧず宸茬‘璁?

## 闃舵涓夛細鎵归噺鎵ц

濮旀墭 `jq-run batch`锛?

```bash
python -m scripts.tools.jq_automation batch <manifest.json> --yes
```

## 闃舵鍥涳細鍒嗘瀽鎶ュ憡

1. 濮旀墭 `jq-analyze` 鐢熸垚鎵规瀵规瘮銆?
2. 鎸?[param-scan-report.md](../templates/param-scan-report.md) 妯℃澘鐢熸垚娣卞害鍒嗘瀽銆?

## 鎶ュ憡瑕佹眰

姣忎竴绔犲繀椤诲寘鍚暟鎹潵婧愬紩鐢紙鍏蜂綋 run_id 鎴?summary_metrics.json锛夈€?
鏁板€煎紩鐢ㄧ簿纭埌 2 浣嶅皬鏁般€?
鎶ュ憡鏍煎紡瑙?[param-scan-report.md](../templates/param-scan-report.md) 妯℃澘銆?
