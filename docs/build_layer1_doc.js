// Layer 1 — Unit Testing — Hands-on Implementation
// Beginner-friendly Word document companion to the LinkedIn strategy article.
//
// Run: node build_layer1_doc.js
// Output: Layer1_Unit_Testing_Implementation.docx
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  TabStopType, TabStopPosition, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak,
} = require('docx');

// ── Style tokens ──────────────────────────────────────────────────────────────
const C = {
  primary:  '1F3A93',
  accent:   '0E7C7B',
  ink:      '1A202C',
  muted:    '4A5568',
  light:    'CBD5E0',
  codebg:   'F5F7FA',
  warnbg:   'FFF4E6',
  warnbar:  'D97706',
};

const border = (color = C.light) => ({ style: BorderStyle.SINGLE, size: 4, color });
const tableBorders = (color = C.light) => ({
  top: border(color), bottom: border(color),
  left: border(color), right: border(color),
  insideHorizontal: border(color), insideVertical: border(color),
});

// ── Convenience builders ──────────────────────────────────────────────────────
const P = (text, opts = {}) => new Paragraph({
  children: [new TextRun({ text, ...opts.run })],
  spacing: { before: 120, after: 120 },
  ...opts.para,
});

const H1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [new TextRun({ text, bold: true, size: 36, color: C.primary, font: 'Calibri' })],
  spacing: { before: 480, after: 240 },
  pageBreakBefore: true,
});

const H2 = (text, opts = {}) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text, bold: true, size: 28, color: C.primary, font: 'Calibri' })],
  spacing: { before: 360, after: 180 },
  ...opts,
});

const H3 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_3,
  children: [new TextRun({ text, bold: true, size: 22, color: C.accent, font: 'Calibri' })],
  spacing: { before: 240, after: 120 },
});

const Body = (text, opts = {}) => new Paragraph({
  children: [new TextRun({ text, size: 22, font: 'Calibri', color: C.ink })],
  spacing: { before: 80, after: 80, line: 320 },
  alignment: AlignmentType.JUSTIFIED,
  ...opts,
});

// Mixed-run body paragraph: pass array of { text, bold?, italic?, code? }
const MixedBody = (runs, opts = {}) => new Paragraph({
  children: runs.map(r => new TextRun({
    text: r.text,
    bold: !!r.bold,
    italics: !!r.italic,
    font: r.code ? 'Courier New' : 'Calibri',
    color: r.code ? C.accent : C.ink,
    size: r.code ? 20 : 22,
    shading: r.code ? { type: ShadingType.CLEAR, fill: C.codebg } : undefined,
  })),
  spacing: { before: 80, after: 80, line: 320 },
  alignment: AlignmentType.JUSTIFIED,
  ...opts,
});

const Bullet = (text) => new Paragraph({
  numbering: { reference: 'bullets', level: 0 },
  children: [new TextRun({ text, size: 22, font: 'Calibri' })],
  spacing: { before: 60, after: 60, line: 300 },
});

const Numbered = (text) => new Paragraph({
  numbering: { reference: 'numbers', level: 0 },
  children: [new TextRun({ text, size: 22, font: 'Calibri' })],
  spacing: { before: 60, after: 60, line: 300 },
});

// Code block — monospace, shaded
const Code = (lines) => {
  if (typeof lines === 'string') lines = lines.split('\n');
  return lines.map((line, i) => new Paragraph({
    children: [new TextRun({
      text: line || ' ',
      font: 'Courier New', size: 18, color: '1A202C',
    })],
    shading: { type: ShadingType.CLEAR, fill: C.codebg },
    spacing: { before: i === 0 ? 120 : 0, after: i === lines.length - 1 ? 120 : 0, line: 260 },
    border: i === 0
      ? { top: { style: BorderStyle.SINGLE, size: 4, color: C.light },
          left: { style: BorderStyle.SINGLE, size: 12, color: C.accent } }
      : { left: { style: BorderStyle.SINGLE, size: 12, color: C.accent } },
    ...(i === lines.length - 1 && {
      border: {
        bottom: { style: BorderStyle.SINGLE, size: 4, color: C.light },
        left:   { style: BorderStyle.SINGLE, size: 12, color: C.accent },
      },
    }),
  }));
};

// Callout box — yellow-orange left border, soft fill
const Callout = (label, body) => {
  return [
    new Paragraph({
      children: [
        new TextRun({ text: label + '  ', bold: true, color: C.warnbar, size: 22, font: 'Calibri' }),
        new TextRun({ text: body, size: 22, color: C.ink, font: 'Calibri' }),
      ],
      shading: { type: ShadingType.CLEAR, fill: C.warnbg },
      border: { left: { style: BorderStyle.SINGLE, size: 16, color: C.warnbar } },
      spacing: { before: 180, after: 180, line: 320 },
    }),
  ];
};

// 2-column / 3-column table — pass rows as 2D string array; first row = header
const SimpleTable = (rows, columnWidths) => {
  const totalWidth = 9360;
  const widths = columnWidths || rows[0].map(() => Math.floor(totalWidth / rows[0].length));
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: widths,
    borders: tableBorders(),
    rows: rows.map((row, rIdx) => new TableRow({
      tableHeader: rIdx === 0,
      children: row.map((cellText, cIdx) => new TableCell({
        width: { size: widths[cIdx], type: WidthType.DXA },
        margins: { top: 100, bottom: 100, left: 140, right: 140 },
        shading: rIdx === 0 ? { type: ShadingType.CLEAR, fill: '1F3A93' } : undefined,
        children: [new Paragraph({
          children: [new TextRun({
            text: cellText,
            bold: rIdx === 0,
            color: rIdx === 0 ? 'FFFFFF' : C.ink,
            size: rIdx === 0 ? 20 : 20,
            font: 'Calibri',
          })],
          spacing: { before: 40, after: 40 },
        })],
      })),
    })),
  });
};

// ── Build the document children ───────────────────────────────────────────────

const children = [];

// ── COVER ──
children.push(new Paragraph({
  children: [new TextRun({ text: ' ', size: 24 })],
  spacing: { before: 1800 },
}));

children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'LLM Testing — Hands-on Implementation',
    bold: true, size: 28, color: C.muted, font: 'Calibri',
  })],
  spacing: { before: 240, after: 120 },
}));

children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'Layer 1',
    bold: true, size: 96, color: C.primary, font: 'Calibri',
  })],
  spacing: { before: 240, after: 120 },
}));

children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'Unit Testing with Metric Libraries',
    bold: true, size: 40, color: C.ink, font: 'Calibri',
  })],
  spacing: { before: 120, after: 360 },
}));

children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'BLEU · ROUGE · METEOR · BERTScore · Exact Match · DeepEval',
    italics: true, size: 24, color: C.accent, font: 'Calibri',
  })],
  spacing: { before: 120, after: 720 },
}));

children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'A beginner-friendly walkthrough of the foundation layer of LLM evaluation. ' +
          'Covers prerequisites (sample bot, golden dataset), every Layer 1 metric, ' +
          'code structure, how to run, and how to read the HTML report.',
    size: 22, color: C.muted, italics: true, font: 'Calibri',
  })],
  spacing: { before: 360, after: 240 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: ' ', size: 24 })],
  spacing: { before: 2400 },
}));

children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'Companion to the 7-Layer LLM Testing Strategy',
    size: 20, color: C.muted, font: 'Calibri',
  })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'Project: llm-eval  ·  Layer 1 of 7',
    size: 18, color: C.muted, font: 'Calibri',
  })],
  spacing: { before: 80 },
}));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 1 — INTRODUCTION
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('1. Why Layer 1 matters'));

children.push(Body(
  'If you tried to run your LLM evaluation suite the way you run unit tests for a regular ' +
  'web service, you would be wrong about almost everything that matters. LLM outputs are ' +
  'probabilistic, not deterministic. Two correct answers can be worded entirely differently. ' +
  'A single hallucinated fact can ride past every assertion you wrote. This is why the ' +
  'strategy document organises LLM testing as a seven-layer pyramid — each layer catches ' +
  'a class of failure the layer below it cannot see.'
));

children.push(Body(
  'Layer 1 is the wide base of that pyramid. It is fast, deterministic, free to run, and ' +
  'runs on every commit. Its job is not to tell you your LLM is excellent — that is ' +
  'what Layers 2, 2.5, and 3 do. Its job is to scream the moment something regresses. ' +
  'If you skip Layer 1, you will find out about quality drops only when a customer ' +
  'complains; if you run Layer 1, you find out within seconds of pushing a commit.'
));

children.push(H2('What this document covers'));

[
  'The two prerequisites you must build before Layer 1 can run: a sample bot and a golden dataset',
  'Each of the six metric definitions from the strategy doc: BLEU, ROUGE-1, ROUGE-2, ROUGE-L, METEOR, BERTScore, Exact Match',
  'The DeepEval add-on layer that wraps two LLM-judge metrics (Answer Relevancy, Hallucination)',
  'How the code is organised: tests/, src/, conftest.py, the HTML reporter',
  'How to run the tests and how to read the report',
  'Common pitfalls and how to calibrate thresholds for your own domain',
].forEach(b => children.push(Bullet(b)));

children.push(...Callout(
  'NEW TO LLM TESTING?',
  'Read the companion strategy article on LinkedIn first. It defines the seven layers and ' +
  'why each exists. This document zooms into Layer 1 only — the foundation. Later articles ' +
  'will cover Layers 2 through 6.'
));

children.push(H2('What you need to have ready'));

children.push(SimpleTable([
  ['Prerequisite', 'Why'],
  ['Python 3.10+', 'Type hints and modern dataclasses used throughout the test code'],
  ['An OpenRouter API key', 'Multi-model gateway. One key gives access to OpenAI, Anthropic, Mistral and others through one OpenAI-compatible API'],
  ['Internet access on first run', 'Downloads the BERTScore transformer (~500 MB) and NLTK wordnet/punkt data (~10 MB). After that, Layer 1 runs fully offline.'],
  ['~50 MB of disk', 'For NLTK corpora and the cached transformer weights'],
], [2400, 6960]));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 2 — PREREQUISITES
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('2. The two prerequisites'));

children.push(Body(
  'Before you can evaluate anything, you need something to evaluate and a definition of what ' +
  '"correct" looks like. In this project, that means a sample bot and a golden dataset. ' +
  'Neither is glamorous; both are foundational. Skipping the work here is the single biggest ' +
  'reason eval projects fail in production.'
));

children.push(H2('2.1  The Sample Bot'));

children.push(Body(
  'For this hands-on, we built a small customer support agent called ShopEasy. It answers ' +
  'questions about returns, refunds, shipping, and order tracking. The whole bot is one short ' +
  'Python file: src/bot.py.'
));

children.push(MixedBody([
  { text: 'The bot is intentionally simple. It has no tools, no retrieval system, no memory — ' +
          'just a system prompt that contains the entire policy knowledge base and one function, ' },
  { text: 'answer(question, context)', code: true },
  { text: ', that calls an LLM through OpenRouter and returns a string. ' +
          'This minimal design means the testing layers are not entangled with bot complexity ' +
          'and the same testing pattern transfers cleanly to any real bot you replace it with.' },
]));

children.push(H3('Why a "sample bot" instead of testing the real one?'));

children.push(Body(
  'You want a reference implementation that always passes Layer 1 when nothing has changed, ' +
  'so when it starts failing you know the suite caught a real regression. A real production ' +
  'bot has constantly-changing prompts, third-party tool integrations, and traffic-driven ' +
  'noise. A reference bot lets you anchor your thresholds against a known-stable baseline ' +
  'first. Once the thresholds are calibrated, you can swap in your real bot.'
));

children.push(H3('What the sample bot looks like'));

children.push(Body('The system prompt embeds the entire policy knowledge base:'));

children.push(...Code([
  'SYSTEM_PROMPT = """You are a helpful customer support agent for ShopEasy.',
  'Answer questions about orders, refunds, and shipping using only the',
  'information provided. Be concise and professional.',
  '',
  'Knowledge base:',
  '- Return window: 30 days from purchase date',
  '- Refund processing: 5-7 business days',
  '- Standard shipping: 3-5 business days, free over $50',
  '- Express shipping: 1-2 business days, $12.99',
  '- Order tracking: use tracking link in confirmation email',
  '- Contact support: support@shopeasy.com or 1-800-555-0199"""',
]));

children.push(Body('And the bot itself is one OpenAI-style chat completion call:'));

children.push(...Code([
  'def answer(question: str, context: str = "") -> str:',
  '    client = OpenAI(',
  '        base_url=os.environ["OPENROUTER_BASEURL"],',
  '        api_key=os.environ["OPENROUTER_API_KEY"],',
  '    )',
  '    user_content = f"Context: {context}\\n\\nQuestion: {question}" if context else question',
  '    resp = client.chat.completions.create(',
  '        model=os.environ["OPENROUTER_MODEL"],',
  '        max_tokens=300,',
  '        messages=[',
  '            {"role": "system", "content": SYSTEM_PROMPT},',
  '            {"role": "user",   "content": user_content},',
  '        ],',
  '    )',
  '    return resp.choices[0].message.content.strip()',
]));

children.push(H2('2.2  The Golden Dataset'));

children.push(Body(
  'A golden dataset is a curated list of input/expected-output pairs. It is the contract ' +
  'between "what the bot should say" and "what the bot does say." Without it, you have ' +
  'no objective signal of regression, only vibes.'
));

children.push(H3('What goes into each golden case'));

children.push(SimpleTable([
  ['Field', 'Purpose'],
  ['id',                  'A short stable identifier (q001, q002…) used in reports and logs'],
  ['question',            'The user input the bot will receive'],
  ['reference',           'The canonical correct answer; what BLEU/ROUGE compare against'],
  ['context',             'Optional RAG-style context passed to the bot'],
  ['retrieved_contexts',  'List of retrieved chunks, needed for Layer 2.5 Ragas later'],
  ['category',            'Tag like "returns" or "shipping" — used for stratified sampling in Layer 3'],
  ['min_rouge_l',         'Per-case ROUGE-L threshold so loose questions can have looser gates'],
], [2700, 6660]));

children.push(Body('Example case from data/golden_dataset.json:'));

children.push(...Code([
  '{',
  '  "id": "q001",',
  '  "question": "What is the return window?",',
  '  "reference": "You can return items within 30 days of purchase.",',
  '  "context": "Return policy: 30 days from purchase date.",',
  '  "retrieved_contexts": [',
  '    "Refunds and returns are valid within 30 days of the purchase date."',
  '  ],',
  '  "category": "returns",',
  '  "min_rouge_l": 0.35',
  '}',
]));

children.push(H3('Who decides the golden dataset in a real project?'));

children.push(Body(
  'No single person. In production teams it is a collaboration: domain experts write the ' +
  'reference answers, product owners define what "good" means beyond facts (tone, refusal ' +
  'rules), engineers turn it into a structured dataset, QA adds adversarial and edge cases, ' +
  'and real user logs seed the question list. The best datasets are not invented by engineers ' +
  'imagining what users will ask — they are sampled from production logs and then ' +
  'annotated by experts.'
));

children.push(...Callout(
  'COMMON FAILURE',
  'Writing the reference answer after seeing the bot output. This anchors your threshold to ' +
  'the current model and gives you a green test that means nothing. Write references first; ' +
  'measure second.'
));

children.push(H3('How big should it be?'));

children.push(Body(
  'For Layer 1, 50–100 cases is enough to anchor thresholds. The strategy doc final principle ' +
  'says it explicitly: "Start with a golden dataset of 50–100 hand-labelled cases." For ' +
  'this project we ship six representative cases — enough to demonstrate the metrics ' +
  'and the report, small enough to read in one screen.'
));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 3 — THE METRICS
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('3. The six Layer 1 metrics'));

children.push(Body(
  'Layer 1 is built around six surface-level metrics defined in the strategy doc. Each one ' +
  'measures a different facet of similarity between the bot output and the reference answer. ' +
  'None of them is sufficient on its own — that is the central design lesson of Layer 1. ' +
  'You combine them so each metric covers the others\' blind spots.'
));

// ── BLEU ──
children.push(H2('3.1  BLEU — Bilingual Evaluation Understudy'));

children.push(MixedBody([
  { text: 'What it measures: ', bold: true },
  { text: 'how many n-grams (sequences of 1 to 4 consecutive words) in the bot ' +
          'output also appear in the reference. Applies a brevity penalty if the bot output is ' +
          'shorter than the reference. Range 0–100.' },
]));

children.push(SimpleTable([
  ['Reference', 'Hypothesis', 'BLEU'],
  ['The cat sat on the mat', 'The cat is on the mat', '≈ 47'],
  ['The cat sat on the mat', 'The cat sat on the mat', '100'],
  ['The cat sat on the mat', 'A feline rested on the rug', '~0'],
], [3300, 3300, 2760]));

children.push(MixedBody([
  { text: 'What it catches: ', bold: true },
  { text: 'word-for-word translation accuracy, structured output (JSON, SQL) consistency.' },
]));
children.push(MixedBody([
  { text: 'What it misses: ', bold: true },
  { text: 'paraphrase. The third row above is a perfectly correct rewording but scores zero.' },
]));
children.push(MixedBody([
  { text: 'Threshold: ', bold: true },
  { text: 'corpus BLEU ≥ 20 for conversational QA; ≥ 50 for translation tasks.' },
]));

// ── ROUGE ──
children.push(H2('3.2  ROUGE-1, ROUGE-2, ROUGE-L'));

children.push(MixedBody([
  { text: 'ROUGE is a family of three metrics that all measure word overlap, but at different ' +
          'granularities.' },
]));

children.push(SimpleTable([
  ['Variant', 'What it counts', 'Stricter than'],
  ['ROUGE-1', 'F1 of single-word overlap',                       'nothing'],
  ['ROUGE-2', 'F1 of two-consecutive-word overlap (bigrams)',     'ROUGE-1'],
  ['ROUGE-L', 'F1 of the longest common subsequence',             'ROUGE-1 (allows reordering)'],
], [1800, 4800, 2760]));

children.push(MixedBody([
  { text: 'What ROUGE catches: ', bold: true },
  { text: 'summarisation quality — did the bot cover the key words from the reference?' },
]));
children.push(MixedBody([
  { text: 'What it misses: ', bold: true },
  { text: 'semantic equivalence. ' },
  { text: '"The patient recovered"', italic: true },
  { text: ' vs ' },
  { text: '"The person healed fast"', italic: true },
  { text: ' scores near zero on every ROUGE variant despite meaning the same thing.' },
]));
children.push(MixedBody([
  { text: 'Thresholds: ', bold: true },
  { text: 'mean ROUGE-1 ≥ 0.40, ROUGE-2 ≥ 0.15, ROUGE-L ≥ 0.30. Use ROUGE-L as your primary ' +
          'because it tolerates word reordering — closer to how humans judge.' },
]));

// ── METEOR ──
children.push(H2('3.3  METEOR — Metric for Evaluation of Translation with Explicit ORdering'));

children.push(Body(
  'METEOR fixes a key blind spot of BLEU and ROUGE: synonyms. It uses WordNet to match ' +
  '"cat" against "feline" and "rested" against "sat." It also applies stemming and a word-order ' +
  'penalty. Range 0–1.'
));

children.push(SimpleTable([
  ['Reference', 'Hypothesis', 'METEOR vs ROUGE-1'],
  ['The cat sat on the mat', 'A feline rested on the rug', 'METEOR ~0.38, ROUGE-1 ~0.0'],
], [3000, 3360, 3000]));

children.push(MixedBody([
  { text: 'Threshold: ', bold: true },
  { text: 'mean METEOR ≥ 0.30. Requires NLTK wordnet download (~10 MB, one-off).' },
]));

// ── BERTScore ──
children.push(H2('3.4  BERTScore'));

children.push(Body(
  'BERTScore is the semantic heavyweight of Layer 1. It computes contextual embeddings for ' +
  'every token in both the candidate and the reference using a transformer model (RoBERTa-large ' +
  'by default), then measures cosine similarity. Returns precision, recall, and F1.'
));

children.push(SimpleTable([
  ['Pair', 'BERTScore F1', 'ROUGE-1'],
  ['"The patient recovered" vs "The person healed fast"', '0.92', '~0.0'],
  ['"30 days" vs "60 days"',                                '0.85', '0.0'],
], [4800, 2280, 2280]));

children.push(...Callout(
  'WATCH OUT',
  'BERTScore tends to give 0.80+ to almost any short English text, even when meanings ' +
  'differ. Treat 0.80 as a floor, not a target — your gate should be ≥ 0.85.'
));

// ── Exact Match ──
children.push(H2('3.5  Exact Match'));

children.push(Body(
  'The simplest metric: 1 if the bot output equals the reference after normalisation ' +
  '(lowercase, strip punctuation, collapse whitespace), 0 otherwise. No partial credit.'
));

children.push(MixedBody([
  { text: 'When to use it: ', bold: true },
  { text: 'structured outputs only. JSON, SQL, code, IDs, prices, contact details. ' +
          'For open-ended QA the exact-match rate is expected to be near zero — that is fine. ' +
          'Use it for the cases where ' },
  { text: 'any', italic: true },
  { text: ' deviation is a failure (e.g. "the cost is 12.99" must contain "12.99" verbatim).' },
]));

// ── When-to-use cheat sheet ──
children.push(H2('3.6  When to use which metric'));

children.push(SimpleTable([
  ['Use', 'Pick'],
  ['Translation, SQL/JSON/code generation', 'BLEU + Exact Match'],
  ['Summarisation',                          'ROUGE-1, ROUGE-2, ROUGE-L'],
  ['Paraphrase tolerance + speed',            'METEOR'],
  ['Semantic equivalence (best general signal)', 'BERTScore F1'],
  ['Critical facts (prices, dates, emails)',  'Exact Match on the token'],
], [4800, 4560]));

children.push(Body(
  'The right answer is always more than one metric. Our Layer 1 test file uses all six and ' +
  'reports them side by side in the HTML output so you can see at a glance which signal is ' +
  'failing.'
));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 4 — CODE WALKTHROUGH
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('4. Code walkthrough'));

children.push(H2('4.1  Project layout for Layer 1'));

children.push(SimpleTable([
  ['File', 'Role'],
  ['src/bot.py',                       'The sample bot (one function, one system prompt)'],
  ['data/golden_dataset.json',         'The 6-case golden dataset'],
  ['conftest.py',                       'pytest fixtures shared across all layers: golden_dataset, bot_outputs, plus the HTML report summary hook'],
  ['tests/test_layer1_metrics.py',     'BLEU + ROUGE + METEOR + BERTScore + Exact Match tests'],
  ['tests/test_layer1_deepeval.py',    'DeepEval Answer Relevancy + Hallucination tests'],
  ['src/reporter.py',                   'HTML report engine — used by every layer'],
  ['src/recommendations.py',            'Failure → suggested fix engine — used by every layer'],
  ['reports/layer1_metrics.html',       'Auto-generated after each run'],
  ['reports/layer1_deepeval.html',      'Auto-generated after each run'],
], [3300, 6060]));

children.push(H2('4.2  The shared fixture — bot_outputs'));

children.push(Body(
  'Every Layer 1 test needs the bot to actually answer each question in the golden dataset. ' +
  'You only want to do that once per test session, not once per test, because each call to ' +
  'the LLM costs money and time. That is what conftest.py does:'
));

children.push(...Code([
  '@pytest.fixture(scope="session")',
  'def golden_dataset():',
  '    with open("data/golden_dataset.json") as f:',
  '        return json.load(f)',
  '',
  '@pytest.fixture(scope="session")',
  'def bot_outputs(golden_dataset):',
  '    # Generate all outputs once per session — avoids repeated API calls',
  '    return [',
  '        {**case, "output": answer(case["question"], case.get("context", ""))}',
  '        for case in golden_dataset',
  '    ]',
]));

children.push(MixedBody([
  { text: 'The ' },
  { text: 'scope="session"', code: true },
  { text: ' is the crucial detail. With it, six bot calls cover every Layer 1 test in the ' +
          'entire run. Without it, you would be re-calling the bot for every metric.' },
]));

children.push(H2('4.3  test_layer1_metrics.py — the surface-level metric tests'));

children.push(Body(
  'The file is organised into one test class per metric. Each class has a per-case test ' +
  '(asserts the score for each individual case) and a dataset-level test (asserts the mean ' +
  'across all cases meets the threshold).'
));

children.push(H3('Per-case ROUGE test'));

children.push(...Code([
  'def test_rouge_per_case(self, bot_outputs):',
  '    """Per-case ROUGE-1, ROUGE-2, ROUGE-L — each must meet its dataset threshold."""',
  '    failures = []',
  '    for case in bot_outputs:',
  '        s   = rouge.score(case["reference"], case["output"])',
  '        thr = case.get("min_rouge_l", THRESHOLDS["rougeL_mean"])',
  '',
  '        _report.add(case["id"], "ROUGE-1",',
  '                    s["rouge1"].fmeasure, THRESHOLDS["rouge1_mean"],',
  '                    s["rouge1"].fmeasure >= THRESHOLDS["rouge1_mean"],',
  '                    actual=case["output"], reference=case["reference"])',
  '',
  '        # … ROUGE-2 and ROUGE-L similarly …',
  '',
  '        if s["rougeL"].fmeasure < thr:',
  '            failures.append(f"{case[\'id\']}: ROUGE-L={s[\'rougeL\'].fmeasure:.3f} < {thr}")',
  '',
  '    assert not failures, "ROUGE-L per-case failures:\\n" + "\\n".join(failures)',
]));

children.push(MixedBody([
  { text: 'Notice the pattern: every test does two things — it asserts on a hard threshold ' +
          '(so pytest fails when the score drops) and it calls ' },
  { text: '_report.add(...)', code: true },
  { text: ' to record the row in the HTML report (so a human can review the score later, ' +
          'pass or fail). Every Layer 1 test follows this pattern.' },
]));

children.push(H3('Per-case BERTScore test'));

children.push(...Code([
  'def test_per_case_bertscore_f1(self, bot_outputs, bs_scores):',
  '    """Per-case BERTScore F1 — no case below 0.70."""',
  '    _, _, F1 = bs_scores       # P, R, F1 — computed once at module scope',
  '    failures = []',
  '    for i, case in enumerate(bot_outputs):',
  '        score  = F1[i].item()',
  '        passed = score >= THRESHOLDS["bertscore_f1_min"]',
  '        _report.add(case["id"], "BERTScore F1", score,',
  '                    THRESHOLDS["bertscore_f1_min"], passed,',
  '                    actual=case["output"], reference=case["reference"])',
  '        if not passed:',
  '            failures.append(f"{case[\'id\']}: F1={score:.3f}")',
  '    assert not failures, "Low BERTScore F1:\\n" + "\\n".join(failures)',
]));

children.push(MixedBody([
  { text: 'The ' },
  { text: 'bs_scores', code: true },
  { text: ' fixture is module-scoped, so BERTScore — which is slow to compute because it loads ' +
          'a transformer model — runs once even though three tests reference it.' },
]));

children.push(H3('The Exact-Match token-presence test'));

children.push(Body(
  'For structured facts (prices, days, emails), we do not check whether the full output equals ' +
  'the reference — we check whether the critical token appears verbatim:'
));

children.push(...Code([
  'STRUCTURED = [',
  '    {"question": "What is the express shipping cost?", "token": "12.99"},',
  '    {"question": "What is the return window?",         "token": "30"},',
  '    {"question": "How do I contact support?",          "token": "support@shopeasy.com"},',
  ']',
  '',
  'def test_exact_token_presence(self, bot_outputs):',
  '    """Critical fact tokens must appear verbatim in output."""',
  '    from src.bot import answer',
  '    failures = []',
  '    for sc in self.STRUCTURED:',
  '        output = answer(sc["question"])',
  '        passed = sc["token"] in output',
  '        _report.add("structured", f"Token present: \'{sc[\'token\']}\'",',
  '                    sc["token"], sc["token"], passed,',
  '                    actual=output, reference=f"must contain \'{sc[\'token\']}\'",',
  '                    note=sc["question"])',
  '        if not passed:',
  '            failures.append(f"\'{sc[\'token\']}\' missing — {sc[\'question\']}")',
  '    assert not failures, "\\n".join(failures)',
]));

children.push(H2('4.4  test_layer1_deepeval.py — Answer Relevancy + Hallucination'));

children.push(Body(
  'DeepEval is a small open-source library that wraps two common LLM-judge metrics. Even ' +
  'though they call an LLM, they belong in Layer 1 in the strategy because they are part of ' +
  'the same fast-feedback CI gate and use the same per-case golden data.'
));

children.push(H3('The OpenRouter LLM wrapper'));

children.push(Body(
  'DeepEval defaults to OpenAI. If you use OpenRouter (or any other provider) the metrics ' +
  'will hit api.openai.com with the wrong key and fail with 401. The fix is a small wrapper:'
));

children.push(...Code([
  'class OpenRouterLLM(DeepEvalBaseLLM):',
  '    def __init__(self):',
  '        self._client = OpenAI(',
  '            base_url=os.environ["OPENROUTER_BASEURL"],',
  '            api_key=os.environ["OPENROUTER_API_KEY"],',
  '        )',
  '        self._model = os.environ["OPENROUTER_MODEL"]',
  '',
  '    def get_model_name(self) -> str: return self._model',
  '    def load_model(self):            return self._client',
  '',
  '    def generate(self, prompt: str) -> str:',
  '        resp = self._client.chat.completions.create(',
  '            model=self._model, max_tokens=1024,',
  '            messages=[{"role": "user", "content": prompt}],',
  '        )',
  '        return resp.choices[0].message.content.strip()',
  '',
  '    async def a_generate(self, prompt: str) -> str:',
  '        import asyncio',
  '        return await asyncio.get_event_loop().run_in_executor(',
  '            None, self.generate, prompt)',
]));

children.push(H3('The Answer Relevancy test'));

children.push(...Code([
  '@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])',
  'def test_answer_relevancy(case, bot_outputs, judge):',
  '    """Each response must be relevant to the question (threshold 0.65)."""',
  '    output = next(o["output"] for o in bot_outputs if o["id"] == case["id"])',
  '    metric = AnswerRelevancyMetric(threshold=0.65, model=judge)',
  '    tc = LLMTestCase(',
  '        input=case["question"], actual_output=output,',
  '        expected_output=case["reference"], context=[case.get("context", "")],',
  '    )',
  '    try:',
  '        assert_test(tc, [metric])',
  '        passed, score = True, metric.score',
  '    except AssertionError:',
  '        passed, score = False, metric.score',
  '',
  '    _report.add(case["id"], "Answer Relevancy", score, 0.65, passed,',
  '                actual=output, reference=case["reference"],',
  '                note=getattr(metric, "reason", ""))',
]));

children.push(MixedBody([
  { text: 'Key detail: ', bold: true },
  { text: 'we capture ' },
  { text: 'metric.score', code: true },
  { text: ' inside both the try and except branches so the score lands in the HTML report ' +
          'whether the assertion passed or failed. Reporting only on the happy path leaves the ' +
          'report mysteriously empty when things go wrong — exactly the moment you need data.' },
]));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 5 — RUNNING
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('5. Running Layer 1'));

children.push(H2('5.1  One-off setup'));

children.push(Numbered('Clone the repo and create a Python 3.10+ virtualenv.'));
children.push(Numbered('Run pip install -r requirements.txt.'));
children.push(Numbered('Create a .env file with OPENROUTER_API_KEY, OPENROUTER_BASEURL, OPENROUTER_MODEL, OPENROUTER_MODEL_JUDGE.'));
children.push(Numbered('Download NLTK data: python -m nltk.downloader -d ~/nltk_data wordnet punkt_tab omw-1.4.'));

children.push(H2('5.2  Running tests'));

children.push(...Code([
  '# Just the surface metrics (BLEU, ROUGE, METEOR, BERTScore, Exact Match)',
  'pytest tests/test_layer1_metrics.py',
  '',
  '# DeepEval (Answer Relevancy + Hallucination — calls the LLM)',
  'pytest tests/test_layer1_deepeval.py',
  '',
  '# Both Layer 1 files together',
  'pytest tests/test_layer1_*.py',
  '',
  '# Run a single class',
  'pytest tests/test_layer1_metrics.py::TestBERTScore -v',
  '',
  '# Re-run only failures from the last run',
  'pytest --lf',
]));

children.push(H2('5.3  Reading the report'));

children.push(Body(
  'When the run finishes, pytest prints a summary block with a clickable file:// link. ' +
  'Cmd-click (macOS) or Ctrl-click (Windows/Linux) it to open the HTML report.'
));

children.push(Body('Every Layer 1 report contains six sections:'));

[
  'Header: layer title, generation timestamp, total assertions, pass/fail banner',
  'Confidence Analysis: HIGH / MEDIUM / LOW band based on pass rate and mean score margin',
  'Recommendations (only when failures exist): prioritised list of concrete fixes',
  'KPI cards: passed, failed, total, pass-rate %',
  'Detailed Results by Metric: collapsible per-metric tables — passing groups auto-collapse, failing ones stay open',
  'Footer: layer ID and timestamp',
].forEach(b => children.push(Bullet(b)));

children.push(H3('What HIGH / MEDIUM / LOW means'));

children.push(SimpleTable([
  ['Confidence', 'Threshold'],
  ['HIGH (green)',   'Pass rate ≥ 90% AND mean score margin ≥ +10% above threshold'],
  ['MEDIUM (amber)', 'Pass rate ≥ 70% OR mean score margin ≥ 0%'],
  ['LOW (red)',      'Pass rate < 70%'],
  ['NOT RUN (grey)', 'No assertions collected (e.g. only metric unit tests ran)'],
], [2400, 6960]));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 6 — RECOMMENDATIONS
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('6. When something fails — the Recommendations engine'));

children.push(Body(
  'A red row in a report is useful. A red row plus "here is what to change in your bot" is ' +
  'far more useful. When Layer 1 has failures, the report includes a Recommendations panel ' +
  'with prioritised, layer-aware suggestions.'
));

children.push(Body('For Layer 1, the engine emits four kinds of recommendations:'));

children.push(SimpleTable([
  ['Failure type', 'Recommendation'],
  ['ROUGE/BLEU low on many cases',
   'Reference phrasing may be too specific — update golden_dataset.json or align bot prompt vocabulary'],
  ['BERTScore F1 low',
   'Real semantic drift — add a few-shot example to SYSTEM_PROMPT showing the desired answer shape'],
  ['Exact-match tokens missing (price, days, email)',
   'Add an instruction to SYSTEM_PROMPT: "Quote prices, days, and contact details verbatim from the knowledge base."'],
  ['Hallucination metric flagged (DeepEval)',
   'Append a grounding instruction at the END of SYSTEM_PROMPT (end-of-prompt instructions weigh more heavily)'],
], [4200, 5160]));

children.push(Body(
  'Every recommendation includes a priority (HIGH/MEDIUM/LOW), a category, the specific file ' +
  'and section to edit, the affected case IDs, and a concrete numbered action plan.'
));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 7 — PITFALLS
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('7. Common pitfalls and how to calibrate'));

children.push(H2('7.1  Pitfall: relying on a single metric'));

children.push(Body(
  'A perfect ROUGE score does not mean a perfect answer; a zero BLEU does not mean a wrong ' +
  'answer. This is why Layer 1 uses six metrics together. If you only run BLEU, every ' +
  'paraphrased correct answer will look like a failure. If you only run BERTScore, you will ' +
  'miss missing facts because BERTScore tolerates 80%+ similarity on almost any short English ' +
  'text.'
));

children.push(H2('7.2  Pitfall: tight thresholds on day one'));

children.push(Body(
  'Do not set BLEU ≥ 50 on a conversational QA bot. BLEU was designed for translation — on a ' +
  'support chatbot, a corpus BLEU of 25 is realistic and meaningful. Run the suite first ' +
  'against your reference bot, observe what scores it actually produces, then set thresholds ' +
  '5–10% below that baseline. This way the test catches regression, not perfection.'
));

children.push(...Callout(
  'PRACTICAL TIP',
  'On day one, run Layer 1 three times against the same bot and dataset. Note the score range. ' +
  'Set your threshold at (lowest observed score) × 0.95. Re-tune monthly.'
));

children.push(H2('7.3  Pitfall: the reference is the bug'));

children.push(Body(
  'When a case is failing every metric, look at the reference first, not the bot. Often the ' +
  'reference is a single rigid phrasing and the bot is producing a perfectly fine alternative. ' +
  'Either rewrite the reference to be more accommodating, or use multi-reference scoring ' +
  '(supported by both BLEU and BERTScore — pass a list of references instead of one).'
));

children.push(H2('7.4  Pitfall: skipping the per-case rows'));

children.push(Body(
  'A mean BERTScore F1 of 0.86 can mask a single case at 0.40. The mean test passes; production ' +
  'fails. Always pair mean tests with per-case floor tests. In this project, both are wired ' +
  'into every metric class — the per-case test reports each case individually and the dataset ' +
  'test asserts the mean.'
));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 8 — SWAPPING LLM PROVIDERS
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('8. Swapping LLM providers — OpenAI, Claude, Gemini'));

children.push(Body(
  'This project uses OpenRouter by default because one API key gives access to every major ' +
  'model (OpenAI, Anthropic, Google, Mistral, and so on) through a single OpenAI-compatible ' +
  'endpoint. That makes it ideal for evaluation work where you want to compare models, but ' +
  'it is not the only option. If you already have an account with one specific vendor, ' +
  'you can swap the provider in just two places for Layer 1:'
));

children.push(Bullet('src/bot.py — the bot under test'));
children.push(Bullet('tests/test_layer1_deepeval.py — the OpenRouterLLM wrapper class'));

children.push(Body(
  'The same swap pattern applies to every other layer (the judge in Layer 2, the Ragas judge ' +
  'in Layer 2.5, the agent runner in Layer 4). The metric logic, thresholds, reporting, and ' +
  'recommendations are all provider-agnostic — only the client construction changes.'
));

// ── OpenAI ──
children.push(H2('8.1  Option A — OpenAI directly'));

children.push(MixedBody([
  { text: 'Install: ', bold: true },
  { text: 'pip install openai', code: true },
]));

children.push(Body('.env additions:'));

children.push(...Code([
  'OPENAI_API_KEY=sk-...',
  'OPENAI_MODEL=gpt-4o-mini          # bot under test (cheaper)',
  'OPENAI_MODEL_JUDGE=gpt-4o         # LLM-as-Judge (stronger)',
]));

children.push(Body('src/bot.py becomes:'));

children.push(...Code([
  'from openai import OpenAI',
  'import os',
  'from dotenv import load_dotenv',
  'load_dotenv()',
  '',
  'def _get_client() -> OpenAI:',
  '    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])',
  '',
  'def answer(question: str, context: str = "") -> str:',
  '    client = _get_client()',
  '    user_content = (f"Context: {context}\\n\\nQuestion: {question}"',
  '                    if context else question)',
  '    resp = client.chat.completions.create(',
  '        model=os.environ["OPENAI_MODEL"],',
  '        max_tokens=300,',
  '        messages=[',
  '            {"role": "system", "content": SYSTEM_PROMPT},',
  '            {"role": "user",   "content": user_content},',
  '        ],',
  '    )',
  '    return resp.choices[0].message.content.strip()',
]));

children.push(MixedBody([
  { text: 'DeepEval — no wrapper needed. ', bold: true },
  { text: 'DeepEval defaults to OpenAI when ' },
  { text: 'OPENAI_API_KEY', code: true },
  { text: ' is set. Just pass the model name when constructing each metric:' },
]));

children.push(...Code([
  'from deepeval.metrics import AnswerRelevancyMetric',
  'metric = AnswerRelevancyMetric(threshold=0.65, model="gpt-4o")',
]));

children.push(...Callout(
  'OPENAI USERS — EASIEST PATH',
  'You can delete the entire OpenRouterLLM class from test_layer1_deepeval.py and just ' +
  'use DeepEval\'s built-in OpenAI support. This is the lowest-friction setup.'
));

// ── Anthropic Claude ──
children.push(H2('8.2  Option B — Anthropic Claude directly'));

children.push(MixedBody([
  { text: 'Install: ', bold: true },
  { text: 'pip install anthropic', code: true },
]));

children.push(Body('.env additions:'));

children.push(...Code([
  'ANTHROPIC_API_KEY=sk-ant-...',
  'ANTHROPIC_MODEL=claude-haiku-4-20250514         # bot (faster, cheaper)',
  'ANTHROPIC_MODEL_JUDGE=claude-opus-4-20250514    # judge (stronger)',
]));

children.push(Body('src/bot.py becomes:'));

children.push(...Code([
  'import anthropic',
  'import os',
  'from dotenv import load_dotenv',
  'load_dotenv()',
  '',
  'def _get_client():',
  '    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])',
  '',
  'def answer(question: str, context: str = "") -> str:',
  '    client = _get_client()',
  '    user_content = (f"Context: {context}\\n\\nQuestion: {question}"',
  '                    if context else question)',
  '    # Claude treats system as a top-level field, NOT a message',
  '    resp = client.messages.create(',
  '        model=os.environ["ANTHROPIC_MODEL"],',
  '        max_tokens=300,',
  '        system=SYSTEM_PROMPT,',
  '        messages=[{"role": "user", "content": user_content}],',
  '    )',
  '    return resp.content[0].text.strip()',
]));

children.push(MixedBody([
  { text: 'Watch out: ', bold: true },
  { text: 'Claude\'s message structure is different. The system prompt is a top-level ' },
  { text: 'system=', code: true },
  { text: ' parameter, not the first item in ' },
  { text: 'messages[]', code: true },
  { text: '. And the response is read via ' },
  { text: 'resp.content[0].text', code: true },
  { text: ', not ' },
  { text: 'resp.choices[0].message.content', code: true },
  { text: '.' },
]));

children.push(Body('tests/test_layer1_deepeval.py — replace the OpenRouterLLM class with:'));

children.push(...Code([
  'import anthropic',
  'from deepeval.models import DeepEvalBaseLLM',
  '',
  'class ClaudeLLM(DeepEvalBaseLLM):',
  '    def __init__(self):',
  '        self._client = anthropic.Anthropic(',
  '            api_key=os.environ["ANTHROPIC_API_KEY"])',
  '        self._model = os.environ["ANTHROPIC_MODEL"]',
  '',
  '    def get_model_name(self): return self._model',
  '    def load_model(self):     return self._client',
  '',
  '    def generate(self, prompt: str) -> str:',
  '        resp = self._client.messages.create(',
  '            model=self._model, max_tokens=1024,',
  '            messages=[{"role": "user", "content": prompt}],',
  '        )',
  '        return resp.content[0].text.strip()',
  '',
  '    async def a_generate(self, prompt: str) -> str:',
  '        import asyncio',
  '        return await asyncio.get_event_loop().run_in_executor(',
  '            None, self.generate, prompt)',
  '',
  '@pytest.fixture(scope="session")',
  'def judge():',
  '    return ClaudeLLM()',
]));

// ── Google Gemini ──
children.push(H2('8.3  Option C — Google Gemini directly'));

children.push(MixedBody([
  { text: 'Install: ', bold: true },
  { text: 'pip install google-genai', code: true },
]));

children.push(Body('.env additions:'));

children.push(...Code([
  'GEMINI_API_KEY=AIza...',
  'GEMINI_MODEL=gemini-2.0-flash             # bot (cheaper)',
  'GEMINI_MODEL_JUDGE=gemini-2.0-pro         # judge (stronger)',
]));

children.push(Body('src/bot.py becomes:'));

children.push(...Code([
  'from google import genai',
  'from google.genai import types',
  'import os',
  'from dotenv import load_dotenv',
  'load_dotenv()',
  '',
  'def _get_client():',
  '    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])',
  '',
  'def answer(question: str, context: str = "") -> str:',
  '    client = _get_client()',
  '    user_content = (f"Context: {context}\\n\\nQuestion: {question}"',
  '                    if context else question)',
  '    resp = client.models.generate_content(',
  '        model=os.environ["GEMINI_MODEL"],',
  '        contents=[user_content],',
  '        config=types.GenerateContentConfig(',
  '            system_instruction=SYSTEM_PROMPT,',
  '            max_output_tokens=300,',
  '        ),',
  '    )',
  '    return resp.text.strip()',
]));

children.push(MixedBody([
  { text: 'Watch out: ', bold: true },
  { text: 'Gemini\'s system prompt lives in a ' },
  { text: 'GenerateContentConfig.system_instruction', code: true },
  { text: ' field passed via the ' },
  { text: 'config=', code: true },
  { text: ' kwarg. There is no separate ' },
  { text: 'messages[]', code: true },
  { text: ' array — the user content goes in ' },
  { text: 'contents=', code: true },
  { text: ' as a list. Response text is at ' },
  { text: 'resp.text', code: true },
  { text: ' (no nesting).' },
]));

children.push(Body('tests/test_layer1_deepeval.py — replace the OpenRouterLLM class with:'));

children.push(...Code([
  'from google import genai',
  'from deepeval.models import DeepEvalBaseLLM',
  '',
  'class GeminiLLM(DeepEvalBaseLLM):',
  '    def __init__(self):',
  '        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])',
  '        self._model  = os.environ["GEMINI_MODEL"]',
  '',
  '    def get_model_name(self): return self._model',
  '    def load_model(self):     return self._client',
  '',
  '    def generate(self, prompt: str) -> str:',
  '        resp = self._client.models.generate_content(',
  '            model=self._model, contents=[prompt],',
  '        )',
  '        return resp.text.strip()',
  '',
  '    async def a_generate(self, prompt: str) -> str:',
  '        import asyncio',
  '        return await asyncio.get_event_loop().run_in_executor(',
  '            None, self.generate, prompt)',
  '',
  '@pytest.fixture(scope="session")',
  'def judge():',
  '    return GeminiLLM()',
]));

// ── Comparison table ──
children.push(H2('8.4  Side-by-side comparison'));

children.push(SimpleTable([
  ['Aspect',                    'OpenRouter',          'OpenAI',          'Claude',                  'Gemini'],
  ['One API for many models',   'Yes',                 'No',              'No',                      'No'],
  ['Latency',                   'adds ~50ms hop',      'direct',          'direct',                  'direct'],
  ['DeepEval out-of-the-box',   'needs wrapper',       'Yes (native)',    'needs wrapper',           'needs wrapper'],
  ['System prompt location',    'messages[0]',         'messages[0]',     'system= top-level',       'config.system_instruction'],
  ['Response shape',            'choices[0].message',  'choices[0].message', 'content[0].text',     'resp.text'],
  ['Best when',                 'comparing models',    'GPT-only stack',  'Claude-only stack',       'Gemini-only stack'],
], [1700, 1700, 1500, 2100, 2360]));

children.push(...Callout(
  'KEY TAKEAWAY',
  'Whichever provider you pick, keep the bot model SEPARATE from the judge model. Use a ' +
  'cheaper, smaller model for the bot under test (what you ship) and a stronger model for ' +
  'the judge (used only in CI). This protects you from self-preference bias and saves money ' +
  'because the bot runs on every commit, but the judge only runs on every PR.'
));

// ─────────────────────────────────────────────────────────────────────────────
// CHAPTER 9 — WHAT'S NEXT
// ─────────────────────────────────────────────────────────────────────────────

children.push(H1('9. What\'s next'));

children.push(Body(
  'Layer 1 is the foundation. It catches the regressions you can detect cheaply, on every commit. ' +
  'But it cannot tell you whether the answer is factually right — only whether it is similar in ' +
  'shape to the reference. That is what Layer 2 (LLM-as-Judge) is for. Layer 2 hands every ' +
  'case to a strong LLM and asks it to score five dimensions: relevance, accuracy, completeness, ' +
  'conciseness, and safety. The companion article for Layer 2 is published separately.'
));

children.push(Body('The hands-on series will cover, one article per layer:'));

[
  'Layer 1 — Unit metric testing (this article)',
  'Layer 2 — LLM-as-Judge (5-dimension scoring with overall score)',
  'Layer 2.5 — Ragas and MLflow framework eval',
  'Layer 3 — Human evaluation, Cohen\'s Kappa, smart sampling',
  'Layer 4 — Agent trajectory evaluation (9 metrics + adversarial injection + multi-turn)',
  'Layer 5 — Security: OWASP ASI Top 10 (2026) red-team harness',
  'Layer 6 — Performance: latency, throughput, regression gates',
].forEach(b => children.push(Bullet(b)));

children.push(...Callout(
  'GET THE CODE',
  'All the code in this article lives in the llm-eval repository. The Layer 1 implementation ' +
  'is fully working — clone, install, drop in your OpenRouter key, and you can be running ' +
  'tests on your own bot within ten minutes.'
));

children.push(Body('— End of Layer 1 article —', { para: { alignment: AlignmentType.CENTER } }));

// ─────────────────────────────────────────────────────────────────────────────
// BUILD AND WRITE
// ─────────────────────────────────────────────────────────────────────────────

const doc = new Document({
  creator: 'llm-eval',
  title:   'Layer 1 — Unit Testing — Hands-on Implementation',
  description: 'Companion article for the 7-Layer LLM Testing Strategy',

  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22 } },
    },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal',
        quickFormat: true,
        run:       { size: 36, bold: true, color: C.primary, font: 'Calibri' },
        paragraph: { spacing: { before: 480, after: 240 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal',
        quickFormat: true,
        run:       { size: 28, bold: true, color: C.primary, font: 'Calibri' },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal',
        quickFormat: true,
        run:       { size: 22, bold: true, color: C.accent, font: 'Calibri' },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 } },
    ],
  },

  numbering: {
    config: [
      { reference: 'bullets',
        levels: [{ level: 0, format: LevelFormat.BULLET, text: '•',
                   alignment: AlignmentType.LEFT,
                   style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: 'numbers',
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.',
                   alignment: AlignmentType.LEFT,
                   style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },

  sections: [{
    properties: {
      page: {
        size:   { width: 12240, height: 15840 },   // US Letter
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({
            text: 'Layer 1 — Unit Testing  ·  llm-eval hands-on series',
            size: 18, color: C.muted, italics: true, font: 'Calibri',
          })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: 'Page ', size: 18, color: C.muted, font: 'Calibri' }),
            new TextRun({ children: [PageNumber.CURRENT], size: 18, color: C.muted, font: 'Calibri' }),
            new TextRun({ text: '  ·  llm-eval', size: 18, color: C.muted, font: 'Calibri' }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = 'Layer1_Unit_Testing_Implementation.docx';
  fs.writeFileSync(out, buf);
  console.log(`✓ ${out} written (${(buf.length / 1024).toFixed(1)} KB)`);
});
