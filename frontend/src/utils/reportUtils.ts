/**
 * 报告内容清理工具函数
 *
 * 移除 LLM 输出中的 thinking/reasoning 内容块，只保留最终报告文本。
 * 兼容历史脏数据：字符串化的 content blocks
 *   [{'type': 'text', 'text': '...'}]
 *   [, {'type': 'text', 'text': '...'}]
 *   [{"type":"text","text":"..."}]
 */

/**
 * 从 pos 处的引号字符串读取完整内容（支持 \\ \" \' \n 等转义）
 * 返回 [解码后的字符串, 结束引号之后的下标]
 */
function readQuotedString(src: string, pos: number): [string, number] | null {
    if (pos >= src.length) return null;
    const quote = src[pos];
    if (quote !== "'" && quote !== '"') return null;

    let i = pos + 1;
    let out = '';
    while (i < src.length) {
        const ch = src[i];
        if (ch === '\\' && i + 1 < src.length) {
            const n = src[i + 1];
            if (n === 'n') out += '\n';
            else if (n === 't') out += '\t';
            else if (n === 'r') out += '\r';
            else if (n === "'" || n === '"' || n === '\\') out += n;
            else out += n; // 保留未知转义字符本身
            i += 2;
            continue;
        }
        if (ch === quote) {
            return [out, i + 1];
        }
        out += ch;
        i += 1;
    }
    return null; // 未闭合
}

/**
 * 在 content-block 字面量中提取所有 type=text 的正文
 */
function extractTextFieldsFromLiteral(block: string): string {
    const chunks: string[] = [];
    const typeTextRe = /['"]type['"]\s*:\s*['"]text['"]/g;
    let tm: RegExpExecArray | null;

    while ((tm = typeTextRe.exec(block)) !== null) {
        // 在 type=text 之后找 text 字段
        const after = block.slice(tm.index);
        const keyMatch = after.match(/['"]text['"]\s*:\s*/);
        if (!keyMatch || keyMatch.index == null) continue;

        const valuePos = tm.index + keyMatch.index + keyMatch[0].length;
        const read = readQuotedString(block, valuePos);
        if (!read) continue;
        const [value] = read;
        const trimmed = value.trim();
        if (trimmed) chunks.push(trimmed);
    }

    if (chunks.length) return chunks.join('\n\n');

    // 兜底：没有 type=text 时，取最长 text 字段（排除 thinking 附近）
    const anyTextKey = /['"]text['"]\s*:\s*/g;
    let best = '';
    let km: RegExpExecArray | null;
    while ((km = anyTextKey.exec(block)) !== null) {
        const valuePos = km.index + km[0].length;
        // 若前面 80 字符内是 thinking，跳过
        const prefix = block.slice(Math.max(0, km.index - 80), km.index);
        if (/thinking|reasoning/.test(prefix)) continue;
        const read = readQuotedString(block, valuePos);
        if (!read) continue;
        if (read[0].length > best.length) best = read[0];
    }
    return best.trim();
}

/**
 * 尝试 JSON.parse 标准 JSON content blocks
 */
function tryParseJsonBlocks(raw: string): string | null {
    const text = raw.trim().replace(/^\[\s*,/, '[');
    if (!text) return null;
    if (!(text.startsWith('[') || text.startsWith('{'))) return null;
    try {
        const parsed = JSON.parse(text);
        return extractFromParsed(parsed);
    } catch {
        return null;
    }
}

function extractFromParsed(parsed: unknown): string | null {
    if (parsed == null) return null;
    if (Array.isArray(parsed)) {
        const parts = parsed
            .map((item) => {
                if (!item || typeof item !== 'object') return '';
                const obj = item as Record<string, unknown>;
                const t = obj.type;
                if (t === 'thinking' || t === 'reasoning' || t === 'tool_use' || t === 'tool_result') {
                    return '';
                }
                if (typeof obj.text === 'string') return obj.text;
                return '';
            })
            .filter(Boolean);
        return parts.length ? parts.join('\n\n').trim() : null;
    }
    if (typeof parsed === 'object') {
        const obj = parsed as Record<string, unknown>;
        const t = obj.type;
        if (t === 'thinking' || t === 'reasoning') return '';
        if (typeof obj.text === 'string') return obj.text;
    }
    return null;
}

/**
 * 用括号平衡找到从 startIdx 的 '[' 开始的完整 list 字面量
 */
function findBalancedList(src: string, startIdx: number): string | null {
    if (src[startIdx] !== '[') return null;
    let depth = 0;
    let inStr: "'" | '"' | null = null;
    let escaped = false;
    for (let i = startIdx; i < src.length; i++) {
        const ch = src[i];
        if (inStr) {
            if (escaped) {
                escaped = false;
                continue;
            }
            if (ch === '\\') {
                escaped = true;
                continue;
            }
            if (ch === inStr) inStr = null;
            continue;
        }
        if (ch === "'" || ch === '"') {
            inStr = ch;
            continue;
        }
        if (ch === '[') depth += 1;
        else if (ch === ']') {
            depth -= 1;
            if (depth === 0) return src.slice(startIdx, i + 1);
        }
    }
    return null;
}

/**
 * 清理单个 block 字面量 → 纯文本
 */
function cleanBlockLiteral(block: string): string {
    const fromJson = tryParseJsonBlocks(block);
    if (fromJson) return fromJson;
    return extractTextFieldsFromLiteral(block);
}

/**
 * 从报告文本中剥离 LLM 的思考过程 / content blocks，只保留最终 Markdown。
 */
export function stripThinkingContent(content: string): string {
    if (!content) return '';

    let text = content;

    // 整段就是 content blocks
    const trimmed = text.trim();
    const wholeLooksLikeBlocks =
        (trimmed.startsWith('[') || trimmed.startsWith('{')) &&
        /['"]type['"]\s*:/.test(trimmed);

    if (wholeLooksLikeBlocks) {
        const cleaned = cleanBlockLiteral(trimmed);
        if (cleaned) text = cleaned;
    }

    // 扫描全文，替换每一个 content-block list
    // 特征：`[` 后不久出现 'type'/'type' 与 text/thinking
    let result = '';
    let i = 0;
    while (i < text.length) {
        const lb = text.indexOf('[', i);
        if (lb < 0) {
            result += text.slice(i);
            break;
        }
        result += text.slice(i, lb);

        // 快速判断是否像 content block list
        const peek = text.slice(lb, lb + 120);
        const looks =
            /\[\s*,?\s*\{/.test(peek) &&
            /['"]type['"]/.test(text.slice(lb, lb + 400));

        if (!looks) {
            result += '[';
            i = lb + 1;
            continue;
        }

        const block = findBalancedList(text, lb);
        if (!block) {
            result += '[';
            i = lb + 1;
            continue;
        }

        // 仅当块内含 type=text/thinking 时才替换
        if (/['"]type['"]\s*:\s*['"](?:text|thinking|reasoning|tool_use|tool_result)['"]/.test(block)) {
            const cleaned = cleanBlockLiteral(block);
            result += cleaned ? `\n\n${cleaned}\n\n` : '';
            i = lb + block.length;
        } else {
            result += '[';
            i = lb + 1;
        }
    }
    text = result;

    // 移除 <think>...</think>
    text = text.replace(/<think>[\s\S]*?<\/think>/gi, '');

    // 移除单独的 thinking 对象
    text = text.replace(
        /\{\s*['"]type['"]\s*:\s*['"]thinking['"]\s*,[\s\S]*?\}\s*,?/g,
        ''
    );

    // 清理空 list / 残留
    text = text.replace(/\[\s*,\s*/g, '[').replace(/\[\s*\]/g, '');

    // 规范化：裸 `json\n{...recommendations...}` → fenced code block
    text = text.replace(/(?:^|\n)json\s*\n(\{)/g, '\n```json\n$1');
    // 若补了开头 fence 但没有结尾，在 recommendations 对象后补结尾
    if (text.includes('```json') && (text.match(/```/g) || []).length % 2 === 1) {
        text = `${text.trimEnd()}\n\`\`\`\n`;
    }

    text = text.replace(/\n{3,}/g, '\n\n').trim();
    return text;
}
