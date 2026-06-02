**Keyword Graph（關鍵詞圖）**是一種將搜尋詞彙與語義關係結構化的方式，本質上是把「關鍵詞集合」轉為「圖結構」。其理論來源主要來自 **資訊檢索（IR）、知識圖譜、語義網路、圖論與搜尋引擎優化（SEO）** 等領域。

  

以下從 **理論基礎 → 基本架構 → 建模方法 → 在 BD leads 系統中的實作** 依序說明。

---

# **一、Keyword Graph 的理論基礎**

  

## **1. Information Retrieval（資訊檢索）**

  

關鍵詞圖最早的思想來自 IR 的 **query expansion** 和 **term association**。

  

核心思想：

- 一個搜尋詞會與其他詞 **共同出現**
    
- 共同出現越多 → 關聯越強
    

  

典型方法：

- **TF-IDF**
    
- **BM25**
    
- **co-occurrence matrix**
    

  

簡化表示：

```
term_i  ↔  term_j
weight = P(term_j | term_i)
```

例如：

```
toy distributor
→ importer
→ wholesaler
→ reseller
```

---

## **2. Semantic Network（語義網路）**

  

語言學中的 **語義網路模型**：

```
concept nodes
+ 
semantic relations
```

例如：

```
AI Toy
 ├ distributor
 ├ importer
 ├ wholesaler
 └ retailer
```

這和 **WordNet / ConceptNet** 的結構類似。

---

## **3. Knowledge Graph（知識圖譜）**

  

Google Knowledge Graph 的基本形式：

```
entity — relation — entity
```

Keyword graph 可以視為 **輕量版知識圖譜**：

```
keyword — related_to — keyword
```

例如：

```
toy distributor → trade fair
toy distributor → toy wholesaler
toy distributor → toy importer
```

---

## **4. Graph Theory（圖論）**

  

Keyword Graph 在數學上就是：

```
G = (V, E)
```

其中：

```
V = keywords
E = relations
```

常見算法：

- PageRank
    
- HITS
    
- Community Detection
    
- Graph Embedding
    

  

這些算法可用於：

- 找核心關鍵詞
    
- 找關鍵詞群
    
- 找長尾關鍵詞
    

---

## **5. Search Engine SEO 理論**

  

SEO 裡有一個概念叫：

  

**Topic Cluster**

  

結構：

```
pillar keyword
  ↳ supporting keywords
```

例如：

```
toy distributor
  ↳ toy importer
  ↳ toy wholesaler
  ↳ toy supplier
```

這其實就是 **keyword graph 的樹狀簡化版本**。

---

# **二、Keyword Graph 的基本架構**

  

一般分為 **四層**：

```
Product Layer
Intent Layer
Role Layer
Context Layer
```

示例：

```
AI toy
   │
   ├ distributor
   │   ├ europe
   │   ├ germany
   │   └ spain
   │
   ├ importer
   │
   └ wholesaler
```

---

## **節點類型**

  

### **1. Product nodes**

```
AI toy
plush toy
designer toy
smart toy
```

---

### **2. Role nodes**

```
distributor
importer
wholesaler
retailer
channel partner
```

---

### **3. Intent nodes**

```
become distributor
looking for distributor
partner program
official distributor
```

---

### **4. Context nodes**

```
europe
germany
spain
trade fair
toy exhibition
```

---

# **三、Keyword Graph 的邊（Edge）**

  

常見關係：

|**relation**|**含義**|
|---|---|
|co-occurrence|同時出現|
|semantic similarity|語義相似|
|intent relation|同一意圖|
|hierarchy|上下位|

例如：

```
toy distributor
  ├ co-occurrence → toy importer
  ├ semantic → toy wholesaler
  ├ intent → looking for distributor
  └ context → europe
```

---

# **四、Keyword Graph 的構建方法**

  

## **方法1：共現矩陣**

```
P(term_j | term_i)
```

例如：

```
toy distributor

共同出現：
importer
wholesaler
supplier
```

建立 adjacency matrix：

```
      importer wholesaler supplier
toy     0.7      0.6        0.4
```

---

## **方法2：Embedding 相似度**

  

利用 embedding：

```
similarity = cosine(vec_i, vec_j)
```

如果：

```
similarity > threshold
```

就建立邊。

  

例如：

```
toy distributor ↔ toy wholesaler
```

---

## **方法3：語義擴展**

  

利用 LLM / embedding：

```
toy distributor
```

擴展：

```
toy importer
toy wholesaler
toy supplier
toy reseller
```

---

# **五、Keyword Graph 在 BD Leads 系統中的作用**

  

主要用於：

  

### **1. Query generation**

  

例如：

```
AI toy distributor europe
plush toy importer germany
designer toy wholesaler spain
```

這些 query 是由 graph 生成。

---

### **2. Search diversification**

  

避免只用一種 query。

  

例如：

```
toy distributor
toy importer
toy wholesaler
toy supplier
```

都可能找到不同公司。

---

### **3. Lead scoring**

  

如果某個網站包含：

```
toy distributor
wholesale
import
```

則 **關鍵詞匹配度更高**。

---

### **4. Query optimization**

  

系統可以自動學習：

```
哪些 query 找到的 leads 最多
```

然後提升權重。

---

# **六、Keyword Graph 的 Mermaid 結構示例**

```mermaid
graph TD
    A[AI Toy] --> B[Distributor]
    A --> C[Importer]
    A --> D[Wholesaler]

    B --> E[Europe]
    B --> F[Germany]
    B --> G[Spain]

    C --> E
    D --> E

    B --> H[Looking for distributor]
    C --> I[Wholesale inquiry]
```

---

# **七、在 LanceDB 中的實作**

  

Keyword graph 可以存成：

```
node table
edge table
```

node：

```
id
keyword
type
embedding
```

edge：

```
source
target
relation
weight
```

然後：

```
query embedding
↓
graph traversal
↓
expand keywords
```

---

# **八、進階模型**

  

高階 Keyword Graph 可以使用：

  

### **Graph Embedding**

  

例如：

- node2vec
    
- DeepWalk
    

  

可以得到：

```
keyword embedding
```

比普通 embedding 更適合搜尋。

---

# **九、最簡單實作架構**

  

實際系統通常用：

```
Keyword Graph
      ↓
Query Generator
      ↓
Search
      ↓
Crawler
      ↓
Lead extraction
```

---

# **十、核心結論**

  

Keyword Graph 本質是：

```
語義網路 + 搜尋 query 擴展
```

理論來源：

1. Information Retrieval
    
2. Knowledge Graph
    
3. Graph Theory
    
4. Semantic Network
    
5. SEO Topic Cluster
    

  

用途：

```
生成搜索詞
擴展搜索範圍
提高lead發現率
```



## **1）单一关键词 → 扩展 → 加权 → 循环强化 → 核心关键词 → 关键线索**


```mermaid
flowchart TD
    A[單一初始關鍵詞<br/>例如: toy distributor] --> B[語義拆解]

    B --> C1[同義詞<br/>distributor / dealer / reseller]
    B --> C2[近義詞<br/>importer / wholesaler / supplier]
    B --> C3[關聯詞<br/>partner program / official distributor / channel]
    B --> C4[代詞與變體<br/>toy company / toy brand / vendor / agent]
    B --> C5[組合詞<br/>toy distributor europe / plush toy importer germany]

    C1 --> D[候選詞池]
    C2 --> D
    C3 --> D
    C4 --> D
    C5 --> D

    D --> E[搜索與採樣]
    E --> F[命中結果分析]

    F --> G1[頻次加權<br/>出現次數]
    F --> G2[共現加權<br/>與高價值詞共同出現]
    F --> G3[轉化加權<br/>是否找到有效lead]
    F --> G4[來源加權<br/>官網 / LinkedIn / 展會名單 / directory]
    F --> G5[區域加權<br/>是否匹配目標市場]
    F --> G6[語義加權<br/>與目標語義距離]

    G1 --> H[綜合評分]
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H
    G6 --> H

    H --> I{是否達到核心詞閾值?}
    I -- 否 --> J[淘汰低價值詞]
    J --> K[保留高分詞]
    K --> L[生成下一輪擴展詞]
    L --> E

    I -- 是 --> M[核心關鍵詞簇]
    M --> N[高價值搜索Query]
    N --> O[關鍵線索入口]

    O --> P[有效公司 / 聯絡頁 / 展會名錄 / LinkedIn / PDF名單]
```

---

## **2）循环强化逻辑：每一轮如何增强拓展能力**


```mermaid
flowchart LR
    A[第1輪<br/>單一詞] --> B[擴展詞池]
    B --> C[搜索驗證]
    C --> D[加權評分]
    D --> E[留下高分詞]

    E --> F[第2輪<br/>高分詞再擴展]
    F --> G[更垂直的組合詞]
    G --> H[搜索驗證]
    H --> I[再次加權]

    I --> J[第3輪<br/>核心詞簇形成]
    J --> K[更高命中率 Query]
    K --> L[更集中線索]
    L --> M[核心市場詞 / 核心角色詞 / 核心信號詞]

    M --> N[持續寫回 Keyword Graph]
    N --> O[未來任務直接調用高表現詞]
```


---

## **3）加权证明有效：为什么每次循环会更强**


```mermaid
flowchart TD
    A[初始詞很寬泛] --> B[擴展出大量候選詞]
    B --> C[用搜索結果做真實市場反饋]
    C --> D[不是靠主觀猜測<br/>而是靠命中結果反饋]

    D --> E1[高頻詞保留]
    D --> E2[高轉化詞加權]
    D --> E3[高可信來源詞加權]
    D --> E4[高共現詞保留]
    D --> E5[低噪音詞保留]

    E1 --> F[下一輪詞池更準]
    E2 --> F
    E3 --> F
    E4 --> F
    E5 --> F

    F --> G[搜索空間收斂]
    G --> H[命中率提高]
    H --> I[有效Lead比例提高]
    I --> J[再反饋進圖譜]
    J --> F
```


---

## **4）线索搜集全流程：搜集 → 去噪 → 清洗 → enrich → 验证 → 完整成果**


```mermaid
flowchart TD
    A[高價值Query] --> B[線索搜集]

    B --> B1[搜索引擎結果<br/>SearXNG / googler / ddgr]
    B --> B2[結構化來源<br/>OpenCorporates / directories / exhibitor list]
    B --> B3[社群來源<br/>LinkedIn / Reddit / X]
    B --> B4[官網與PDF<br/>about / contact / distributor / partner]

    B1 --> C[原始結果池]
    B2 --> C
    B3 --> C
    B4 --> C

    C --> D[去噪]
    D --> D1[去重<br/>domain / company / linkedin]
    D --> D2[去垃圾來源<br/>聚合站 / 無效頁 / 低可信]
    D --> D3[去非目標市場]
    D --> D4[去非目標角色]

    D1 --> E[結果清洗]
    D2 --> E
    D3 --> E
    D4 --> E

    E --> E1[標準化公司名]
    E --> E2[標準化網址]
    E --> E3[標準化國家地區]
    E --> E4[抽取Email / LinkedIn / Contact頁]
    E --> E5[抽取角色與渠道信號]

    E1 --> F[Enrich]
    E2 --> F
    E3 --> F
    E4 --> F
    E5 --> F

    F --> F1[公司資料補全]
    F --> F2[官網 about/contact 補抓]
    F --> F3[LinkedIn 補充]
    F --> F4[展會與目錄交叉比對]
    F --> F5[歷史記憶匹配<br/>LanceDB / CRM]

    F1 --> G[驗證]
    F2 --> G
    F3 --> G
    F4 --> G
    F5 --> G

    G --> G1[是否有真實公司主體]
    G --> G2[是否有可聯繫方式]
    G --> G3[是否符合目標市場]
    G --> G4[是否符合目標角色]
    G --> G5[是否有商業合作信號]

    G1 --> H[最終打分]
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H

    H --> I{是否達標?}
    I -- 否 --> J[歸檔為低優先級 / 待觀察]
    I -- 是 --> K[完整成果]

    K --> K1[Lead 卡片]
    K --> K2[CRM 寫入]
    K --> K3[跟進建議]
    K --> K4[郵件草稿]
    K --> K5[回寫 Keyword Graph]
```


---

## **5）把两套流程接起来：从关键词图到完整 lead 成果**


```mermaid
flowchart LR
    A[單一關鍵詞] --> B[Keyword Graph 擴展]
    B --> C[加權循環強化]
    C --> D[核心關鍵詞簇]
    D --> E[高價值Query]
    E --> F[線索搜集]
    F --> G[去噪]
    G --> H[清洗]
    H --> I[Enrich]
    I --> J[驗證]
    J --> K[完整Lead成果]
    K --> L[回寫記憶與Keyword Graph]
    L --> B
```


---

## **6）如果你想在文档里再落到“可执行字段”，建议加这组评分维度**

  

你可以在图下面再配一段说明：

```
綜合評分 = 
0.25 * 頻次分
+ 0.20 * 共現分
+ 0.20 * 轉化分
+ 0.15 * 來源可信度
+ 0.10 * 區域匹配度
+ 0.10 * 語義相似度
```

Lead 最终评分也可以类似：

```
Lead Score =
0.25 * 公司匹配度
+ 0.20 * 聯繫完整度
+ 0.20 * 渠道信號強度
+ 0.15 * 市場匹配度
+ 0.10 * 來源可信度
+ 0.10 * 最近活躍度
```

# **一、Query Refinement（查詢精煉）**

  

最直接的概念就是 **Query Refinement / Query Reformulation**。

  

核心思想：

```
第一次搜索 → 觀察結果 → 調整 query → 再搜索
```

每一次循環：

- 增加精準詞
    
- 排除噪音詞
    
- 收斂結果
    

  

典型流程：

```
initial query
↓
analyze results
↓
add constraints
↓
exclude noise
↓
re-run search
```

例子：

```
toy distributor

→ toy distributor europe
→ toy distributor europe -retail
→ toy distributor europe -retail -amazon
→ "toy distributor" europe importer
```

---

# **二、Boolean Retrieval（布林檢索）**

  

搜尋引擎最早的理論之一。

  

核心：

```
AND
OR
NOT
```

例如：

```
toy AND distributor
toy AND (distributor OR importer)
toy distributor NOT retail
```

Google 其實在背後仍然使用類似邏輯。

---

# **三、Search Operators（進階搜尋運算符）**

  

這就是你說的「**進階搜尋運算符**」。

  

常見：

|**operator**|**作用**|
|---|---|
|site:|限定網站|
|intitle:|限定標題|
|inurl:|限定網址|
|filetype:|限定文件|
|“”|精確短語|

- | 排除詞 |
    

  

例子：

```
toy distributor europe site:linkedin.com
"toy distributor" europe -retail -shop
toy importer germany filetype:pdf
```

---

# **四、Iterative Query Expansion（迭代式查詢擴展）**

  

與 Keyword Graph 結合的理論。

  

流程：

```
keyword
↓
search
↓
extract new terms
↓
expand query
↓
search again
```

例如：

```
toy distributor
↓
results show "wholesale toy supplier"
↓
next query
toy wholesale supplier europe
```

這種方法在：

- academic IR
    
- 搜索引擎
    
- OSINT
    

  

都很常見。

---

# **五、Relevance Feedback（相關性回饋）**

  

資訊檢索裡很重要的概念。

  

流程：

```
query
↓
results
↓
標記哪些相關
↓
系統調整 query
```

數學形式：

```
new query =
original query
+ α * relevant terms
- β * irrelevant terms
```

這就是：

  

**Rocchio Algorithm**

---

# **六、Noise Filtering（噪音過濾）**

  

當搜尋結果包含很多垃圾資訊時。

  

方法：

```
negative keywords
domain filtering
content scoring
```

例如：

```
toy distributor europe
-retail
-shop
-amazon
-ebay
```

---

# **七、OSINT 中的 Dorking**

  

在調查領域叫：

  

**Google Dorking**

  

例如：

```
"toy distributor" europe filetype:pdf
site:linkedin.com "toy distributor"
intitle:"toy distributor"
```

---

# **八、這整套方法在工程上叫**

  

### **Search Query Optimization**

  

或者：

```
Query Optimization
Search Refinement
Iterative Search
```

---

# **九、可以用 Mermaid 表達這個流程**

````
```mermaid
flowchart TD
    A[初始關鍵詞] --> B[第一次搜索]

    B --> C[分析結果]

    C --> D1[增加精準詞]
    C --> D2[排除噪音詞]
    C --> D3[加入進階運算符]
    C --> D4[擴展關聯詞]

    D1 --> E[新Query]
    D2 --> E
    D3 --> E
    D4 --> E

    E --> F[再次搜索]

    F --> G[結果評估]

    G --> H{是否足夠精準}

    H -- 否 --> C
    H -- 是 --> I[高質量結果]
```
````

---

# **十、加入 Operator 的版本**

````
```mermaid
flowchart TD
    A[初始Query] --> B[搜索]

    B --> C[結果分析]

    C --> D1[加入site限制]
    C --> D2[加入filetype限制]
    C --> D3[加入精確短語]
    C --> D4[加入NOT排除詞]

    D1 --> E[Query Refinement]
    D2 --> E
    D3 --> E
    D4 --> E

    E --> F[重新搜索]

    F --> G[噪音下降]
    G --> H[結果更精準]

    H --> I{是否達標}

    I -- 否 --> C
    I -- 是 --> J[有效線索]
```
````

---

# **十一、與你的 BD leads 系統結合**

  

這個流程應該在：

```
Keyword Graph
↓
Query Generator
↓
Query Optimization
↓
Search
```

結構：

```
keyword graph
↓
query
↓
operator refinement
↓
search
↓
lead discovery
```

---

# **十二、總結**

  

你描述的這套其實是這些理論的組合：

|**概念**|**說明**|
|---|---|
|Query Refinement|查詢精煉|
|Boolean Retrieval|布林檢索|
|Search Operators|進階運算符|
|Iterative Search|迭代搜尋|
|Relevance Feedback|相關性回饋|
|Noise Filtering|噪音過濾|
|Google Dorking|OSINT 搜索|

本質是一種：

```
Iterative Search Optimization
```

---
下面给出 **两张“窄版、LLM友好”的 Mermaid 流程图**。

特点：

- **纵向（TD）结构**，适合 Obsidian 窄屏
    
- 每个节点 **短文本**，避免过宽
    
- **分阶段**，方便 LLM 执行与审计
    
- 包含：
    
    - Keyword 扩展与循环加权
        
    - Query 运算符优化
        
    - Lead 采集与清洗流程
        
    

  

直接复制到 Obsidian 即可。

---

# **1）Keyword 扩展 + 循环强化（窄版）**


```mermaid
flowchart TD

A[Seed Keyword]
A --> B[Expand Terms]

B --> C1[Synonyms]
B --> C2[Near Words]
B --> C3[Related Terms]
B --> C4[Variants]
B --> C5[Phrase Combos]

C1 --> D[Candidate Pool]
C2 --> D
C3 --> D
C4 --> D
C5 --> D

D --> E[Search Test]

E --> F[Result Analysis]

F --> G1[Freq Score]
F --> G2[Cooccur Score]
F --> G3[Lead Score]
F --> G4[Source Score]

G1 --> H[Weighted Score]
G2 --> H
G3 --> H
G4 --> H

H --> I{Core Term?}

I -->|No| J[Prune Noise]
J --> K[Keep High Score]
K --> B

I -->|Yes| L[Core Keyword Set]

L --> M[Generate Queries]
M --> N[Lead Discovery]
```


---

# **2）Query Refinement（進階搜尋運算符）**


```mermaid
flowchart TD

A[Base Query]

A --> B[Search Engine]

B --> C[Inspect Results]

C --> D1[Add Phrase ""]
C --> D2[Add Site Filter]
C --> D3[Add Filetype]
C --> D4[Add NOT -noise]

D1 --> E[Refined Query]
D2 --> E
D3 --> E
D4 --> E

E --> F[Re-run Search]

F --> G[Noise Reduced]

G --> H{Precise?}

H -->|No| C
H -->|Yes| I[High Value URLs]
```


---

# **3）Lead 搜集 → 去噪 → Enrich → 驗證（窄版）**


```mermaid
flowchart TD

A[High Value Query]

A --> B[Collect Sources]

B --> B1[Search]
B --> B2[Directories]
B --> B3[LinkedIn]
B --> B4[PDF Lists]

B1 --> C[Raw Pool]
B2 --> C
B3 --> C
B4 --> C

C --> D[De-noise]

D --> D1[Remove Duplicates]
D --> D2[Remove Spam]
D --> D3[Remove Wrong Region]

D1 --> E[Clean Data]
D2 --> E
D3 --> E

E --> F[Enrich]

F --> F1[Company Info]
F --> F2[Contact Page]
F --> F3[LinkedIn]
F --> F4[Cross Check]

F1 --> G[Validation]
F2 --> G
F3 --> G
F4 --> G

G --> H{Valid Lead?}

H -->|No| I[Archive]
H -->|Yes| J[Lead Record]

J --> K[CRM Entry]
J --> L[Follow-up Draft]
```


---

# **4）完整管线（超窄版总览）**

  

如果你想在文档最上面放一个 **整体流程图**：


```mermaid
flowchart TD

A[Seed Keyword]

A --> B[Keyword Graph]
B --> C[Query Builder]
C --> D[Query Refinement]
D --> E[Search]

E --> F[Crawler]
F --> G[De-noise]
G --> H[Clean]

H --> I[Enrich]
I --> J[Validate]

J --> K[Lead Output]

K --> L[Memory Update]
L --> B
```


---

# **5）為什麼這種結構對 LLM 更友好**

  

原因有三個：

  

### **1. 每一步都是單一職責**

  

例如：

```
Expand Terms
Search Test
Result Analysis
```

LLM 更容易拆任務。

---

### **2. 循環點明確**

```
Score → Prune → Expand
```

這是典型 **Relevance Feedback Loop**。

---

### **3. 圖寬控制**

  

所有節點都：

```
<20 characters
```

Obsidian 不會撐爆。

---

# **6）如果要再升級一層（推薦）**

  

未來你可以把整套系統拆成 **四個 agent**：

```
Keyword Agent
Search Agent
Extraction Agent
Validation Agent
```

然後：

```
LanceDB → memory
Jina → embeddings
OpenClaw → orchestration
```

整個就會變成一個 **可自我強化的 BD discovery system**。

---
