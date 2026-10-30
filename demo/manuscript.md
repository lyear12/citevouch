# 构式语法研究总档（节选 · citevouch 演示）

> 这份节选保留了原档的【原文】/【实测】/【推测】三级标记约定，只是把
> "可逐条比对的断言"改写成了 citevouch 能读出证据的 claim 块。
> 真档在 `C:/Users/31887/Desktop/构式语法文献包/构式语法研究总档.md`。

## 7.4 关键数据

```claim id=cxn-total source=vaneecke2026cxn ref=vaneecke2026learning page=6
quote: |
  The resulting grammar consists of a network of 40,688 constructions, of which 9,800 are frame-
  evoking constructions, 22,568 are argument structure constructions and 8,320 are roleset construc-
  tions.
claim: |
  构式总数为 40,688，其中框架触发 9,800、论元结构 22,568、角色集 8,320。
```

```claim id=corpus-size source=vaneecke2026cxn ref=vaneecke2026learning page=6
quote: |
  Together, the combined corpus contains 154,391 utterances, annotated with a total of 440,528
  roleset instances.
claim: |
  训练语料合计 154,391 句 / 440,528 个角色集实例。
```

```claim id=hapax-share source=vaneecke2026cxn ref=vaneecke2026learning page=7
quote: |
  we observe that almost half of the constructions of the network (48.4%) occur only once in the
  corpus
claim: |
  48.4% 的构式为 hapax（只出现一次）。
```

```claim id=avg-degree source=vaneecke2026cxn ref=vaneecke2026learning page=14
quote: |
  Average degree (argst-roleset): 6.35 Average degree (fe-roleset): 1.46 Average degree (fe-argst): 5.47
claim: |
  网络平均度：论元结构↔角色集 6.35；框架触发↔角色集 1.46；框架触发↔论元结构 5.47。
```

## 7.5 一个引用

```claim id=fcg-editor source=cxgbert2020 ref=cxgbert2020
quote: |
  The FCG Editor is an innovative environment for engineering computational construction grammars.
claim: |
  FCG Editor 是工程化计算构式语法的环境。
```

## 8 复刻手册（这些断言还没有绑定证据）

【原文】PyFCG 3.3 可正常安装，论文所列 API 全部实装且命名一致。

【推测】把 40,688 条构式灌进 CxGBERT 的输入表示，能提升 NPN 构式的判定准确率约 3–5 个点。
