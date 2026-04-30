# Benchmark Notes: Vision-Capable LLMs on Scientific Figure Interpretation

## Task

I compared several vision-capable LLMs on the same prompt:

> "please analyze the attached plots"

The input was a cropped scientific figure showing visible panels **a–c**.

## Ground Truth Used for Evaluation

Only the visibly supported content in the image was used for judging the responses.

### Panel a
Visible elements:
- **ExP library**
- **DNase-seq**
- **Gene promoters**
- **Enhancers**
- promoter annotation around **+20 bp**
- construct with labeled segments **264 bp / 300 bp / 264 bp**
- labels **BC** and **pA**
- steps:
  - **Build promoter–BC–enhancer dictionary**
  - **Transfect K562 cells for 24 h**
  - **STARR-seq expression = RNA/DNA**

### Panel b
Visible elements:
- density/scatter-style replicate comparison
- **R² = 0.92**
- axes compare **STARR-seq expression**
  - **replicates 1 and 2**
  - **replicates 3 and 4**

### Panel c
Visible elements:
- y-axis: **Average promoter activity (RNA/DNA)**
- groups:
  - **Genomic ctrls (n = 95)**
  - **Not expressed (n = 20)**
  - **Expressed (n = 870)**
- labeled examples:
  - **RPL3**
  - **HSP90AA1**
  - **ACTB**
  - **MYC**
  - **HBE1**
  - **GATA1**

---

## Model Mapping

| Response | Model | Access | Cost |
|---|---|---|---|
| #1 | `qwen/qwen3.6-35b-a3b Q4_K_M` | local | free |
| #2 | `google/gemma-4-26b-a4b Q4_K_M` | local | free |
| #3 | `ChatGPT 5.4 Thinking Extended` | web | not free |
| #4 | `Gemini 3.1 Pro Preview` | web | not free |
| #5 | `zai-org/glm-4.6v-flash Q4_K_M` | local | free |

---

## Processing Speed

| Response | Model | Processing Time |
|---|---|---:|
| #1 | `qwen/qwen3.6-35b-a3b Q4_K_M` | 52 s |
| #2 | `google/gemma-4-26b-a4b Q4_K_M` | 6.5 s |
| #3 | `ChatGPT 5.4 Thinking Extended` | 58 s |
| #4 | `Gemini 3.1 Pro Preview` | 25 s |
| #5 | `zai-org/glm-4.6v-flash Q4_K_M` | 6.3 s |

---

## Overall Ranking

| Rank | Response | Model | Access | Speed | Rating | Verdict |
|---|---:|---|---|---:|---:|---|
| **1** | **#3** | **ChatGPT 5.4 Thinking Extended** | web, not free | **58 s** | **8.8/10** | Best overall; strongest balance of accuracy, restraint, and correct interpretation |
| **2** | **#4** | **Gemini 3.1 Pro Preview** | web, not free | **25 s** | **8.1/10** | Very good and detailed; slightly more overreach than #3 |
| **3** | **#2** | **google/gemma-4-26b-a4b Q4_K_M** | local, free | **6.5 s** | **6.9/10** | Best speed/quality tradeoff among the fast local models |
| **4** | **#1** | **qwen/qwen3.6-35b-a3b Q4_K_M** | local, free | **52 s** | **6.3/10** | Acceptable, but slower than expected for its quality here |
| **5** | **#5** | **zai-org/glm-4.6v-flash Q4_K_M** | local, free | **6.3 s** | **2.0/10** | Fast, but clearly the least reliable on this figure |

---

## Per-Response Assessment

| Response | Overall | What it got right | Main mistakes / overreach |
|---|---:|---|---|
| **#3** | **8.8/10** | Best balance of accuracy and restraint. Correctly read the overall assay logic, strong reproducibility in panel b, and higher activity for the expressed group in panel c. Also appropriately noted that only panels a–c were visible. | Slightly less complete than #4: did not explicitly report the visible sample sizes (**95 / 20 / 870**). Some interpretation beyond pure visual reading, but still reasonable. |
| **#4** | **8.1/10** | Best quantitative reading. Correctly captured **+20 bp**, **264/300/264 bp**, **R² = 0.92**, and the **95 / 20 / 870** counts. Correctly treated the labeled genes in panel c as highlighted examples within the expressed group. | Added several things not directly shown in the figure: e.g. “randomly generated barcodes,” details about RNA content, and extra biological background. Also called **R²** a “Pearson correlation coefficient,” which is imprecise wording. |
| **#2** | **6.9/10** | Good overall structure. Correctly read panel b and the **95 / 20 / 870** counts in panel c. | Misread the construct in panel a by effectively making **BC = 300 bp**, which the figure does not directly show. Also blurred the distinction between plot categories and inferred assay-defined classes. |
| **#1** | **6.3/10** | Got the broad storyline mostly right: assay design, reproducibility, and stronger activity in the expressed class. | Several visible-number errors: read the groups as **n = 99** and **n = 570** instead of **95** and **870**. Also used words like “significant” without visible statistical support in the figure. |
| **#5** | **2.0/10** | Recognized that panel b was about reproducibility and that panel a was a STARR-seq workflow. | Clearly the weakest. Badly misread panel c: the boxplots are **not gene-specific boxplots**, the labeled genes are highlighted points, and it reversed the sample sizes by saying **expressed n = 20** and **non-expressed n = 870**. Also garbled some labels. |

---

## Main Takeaways

### Best overall quality
**ChatGPT 5.4 Thinking Extended** (#3)

### Best runner-up
**Gemini 3.1 Pro Preview** (#4)

### Best local/free option
**google/gemma-4-26b-a4b Q4_K_M** (#2)

### Most disappointing speed/quality balance
**qwen/qwen3.6-35b-a3b Q4_K_M** (#1)  
It was much slower than Gemma but not better enough to justify the time in this test.

### Fastest but least reliable
**zai-org/glm-4.6v-flash Q4_K_M** (#5)

---

## Practical Interpretation

If the goal is **most trustworthy scientific figure reading**, then for this test:

**ChatGPT 5.4 Thinking Extended > Gemini 3.1 Pro Preview > Gemma 4 26B > Qwen 3.5 35B >>> GLM-4.6V-Flash**

If the goal is **speed/quality tradeoff**:
- **Gemini** looks especially strong because it stays near the top in quality while being much faster than ChatGPT.
- **Gemma** is very attractive for a **local/free** workflow because it is fast and still reasonably solid.
- **Qwen** did not justify its longer runtime in this particular comparison.
- **GLM** was fast, but too error-prone for reliable scientific figure interpretation.

---

## One-Line Summary

For this single scientific-figure analysis task, **ChatGPT 5.4 was best overall, Gemini was the best high-quality faster option, Gemma was the best local/free compromise, Qwen was slower than its result justified, and GLM was fast but unreliable.**

---

## Caveat

This benchmark is based on **one image and one prompt only**.  
So this is a useful qualitative comparison for **scientific figure reading under this task setup**, but not a general ranking of all model vision performance.