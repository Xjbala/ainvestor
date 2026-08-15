/**
 * 统一时间格式化工具
 * 所有组件使用此函数确保时区一致
 */

/**
 * 将 ISO 时间戳格式化为本地时间
 * @param timestamp ISO 8601 时间字符串
 * @returns 格式化的本地时间字符串 (HH:MM)
 */
export function formatTime(timestamp: string): string {
    try {
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) return '--:--:--';
        return date.toLocaleTimeString('zh-CN', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    } catch {
        return timestamp;
    }
}

/**
 * 格式化为短时间 (HH:MM)
 */
export function formatTimeShort(timestamp: string): string {
    try {
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) return '--:--';
        return date.toLocaleTimeString('zh-CN', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return timestamp;
    }
}

/**
 * 格式化日期时间 (YYYY-MM-DD HH:MM)
 */
export function formatDateTime(timestamp: string): string {
    try {
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) return '--';
        return date.toLocaleString('zh-CN', {
            hour12: false,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return timestamp;
    }
}
