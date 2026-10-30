# V2EX

*发在「分享创造」节点。V2EX 的读者会真的 clone 下来跑，也会立刻指出你没说清楚的地方——所以正文里把「它不做什么」写在前面的半段，比堆功能有用。*

---

**标题**

```
[分享创造] 写了个工具，把论文里的每个数字钉在 PDF 的那一页上
```

---

**正文**

写论文的人大概都干过这件事：正文里写着「语料共 154,391 句」，这个数字确实在某篇论文里，但它到底在第 6 页，还是在你上一版草稿里，还是你从另一篇论文里记混了？

查重工具查的是文字，文献管理软件管的是格式，DOI 检查器查的是「这篇论文是否存在」。没有东西替你回答「你写下的这句话，在你手上这份 PDF 的第几页，能不能逐字找到」。

所以我写了一个，叫 citevouch。

**它怎么用**

在想要被核对的那句话旁边写一个块，块里写清楚：哪份 PDF、第几页、逐字原文。

````
```claim id=cxn-total source=vaneecke2026cxn page=6
quote: |
  The resulting grammar consists of a network of 40,688 constructions, of which
  9,800 are frame-evoking constructions, 22,568 are argument structure
  constructions and 8,320 are roleset constructions.
claim: |
  The induced construction network has 40,688 constructions.
```
````

`citevouch scan` 把这段话存进一个可以提交进 git 的账本；`citevouch verify` 重新打开 PDF，告诉你哪些引文还在它该在的那一页、哪些挪了位置、哪些已经找不到了。

**为什么不是「又一个引文检查器」**

| | 查什么 | 抓得住 | 抓不住 |
|---|---|---|---|
| DOI / 元数据检查器 | 引文在 Crossref 能不能解析 | 幻觉引用、撤稿、年份错 | 真论文被引错内容 |
| 文献管理软件 | 格式、重复条目 | — | 一切语义问题 |
| citevouch | 这句话 ↔ 那个文件的哪一页 | 抄错的数字、漂成转述的引文、被换成新版/另一版的 PDF | 论文本身好不好 |

**三件我觉得值得说的**

1. **它会对着真人论文说「不」。** 仓库里自带的 demo 有 5 条断言，4 条通过，第 5 条引的那句话在另一篇论文里——那条每次都会失败，是故意的。哪天它通过了，说明匹配变松了，那是 bug。
2. **完全离线。** 不连 Crossref、不上报任何东西，只读你盘上的文件。这是约束不是卖点：正因为只读本地文件，它才敢说「这句话在第 6 页」，而不是「这个 DOI 存在」。
3. **有个 `draft` 命令。** 读你现有的稿子，把每处 `[@key]`、`\cite{key}` 找出来，自动给出候选块让你审。手写一百个这种块，就是这类工具没人用的原因。

**.tex 直接能读**，`draft paper.tex --bib refs.bib` 就行。`scan` / `verify` 永远不需要读 .tex——它们读的是 PDF。

**它不做什么（先说清楚省得白装）**

- 不联网，所以查不了「论文是否被撤稿」——那是 citegate 一类工具的事，两者互补。
- 不做 OCR。扫描版 PDF 需要你先跑一遍 OCR 或者准备好文本版。
- 不判断论文本身好不好，只判断你的陈述和原文对不对得上。
- 不是 TeX 解析器。宏展开、`\input` 这类会读成正文或者跳过，结果是候选块变弱，不会是假通过。

**装**

```sh
pip install "git+https://github.com/lyear12/citevouch@v0.16.3"
cd demo && citevouch verify manuscript.md
```

两条命令就能看到它对着一篇真论文说「这条不对」。

还没上 PyPI（trusted publisher 要人登录一次，我还没做），所以上面这个从 git 装的写法是当前可用的。

GitHub: https://github.com/lyear12/citevouch
Python / MIT / 除 pypdf 外无运行时依赖

---

## 发帖备注

- **别用「AI 全自动写的」当标题。** V2EX 上这个词会招来一整串关于 AI 的回复，而且不会有人去跑 demo。如果被问到就直说，但别拿它当卖点——真正有价值的是「它会说是错的」这件事。
- **自己先把 demo 跑一遍再发。** 帖子里贴的三条命令必须在你自己机器上验证过，V2EX 的读者真的会照着敲，报错会第一个出现在评论区。
- **准备好回答「为什么不直接上 PyPI」。** 诚实回答：trusted publisher 是账号操作，需要人登录一次。别绕。
- **不要跨节点重复发。** 一个节点发一次，被下沉了也别重发。
