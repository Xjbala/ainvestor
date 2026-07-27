/**
 * 公司搜索输入组件
 *
 * 供财务报表/年报/新闻查看页共用，输入股票代码或名称搜索并选择公司。
 */

import React, { useState, useEffect, useRef } from 'react';
import { Search, X } from 'lucide-react';
import { companiesApi } from '../../services/companiesApi';

// 复用 companiesApi 的类型
interface CompanyOption {
    stock_code: string;
    stock_name: string;
}

interface CompanySearchInputProps {
    value: string;
    onChange: (code: string) => void;
    placeholder?: string;
}

export const CompanySearchInput: React.FC<CompanySearchInputProps> = ({
    value,
    onChange,
    placeholder = '输入股票代码或名称搜索...',
}) => {
    const [query, setQuery] = useState(value);
    const [options, setOptions] = useState<CompanyOption[]>([]);
    const [showDropdown, setShowDropdown] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // 搜索
    useEffect(() => {
        if (!query || query.length < 1) {
            setOptions([]);
            return;
        }
        const timer = setTimeout(async () => {
            setIsLoading(true);
            try {
                const resp = await companiesApi.listCompanies(1, 20, query);
                const items = resp.items;
                setOptions(
                    Array.isArray(items)
                        ? items.map((c: { stock_code: string; stock_name: string }) => ({
                              stock_code: c.stock_code,
                              stock_name: c.stock_name,
                          }))
                        : []
                );
                setShowDropdown(true);
            } catch {
                setOptions([]);
            } finally {
                setIsLoading(false);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [query]);

    // 点击外部关闭
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setShowDropdown(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const handleSelect = (code: string, name: string) => {
        setQuery(`${code} ${name}`);
        onChange(code);
        setShowDropdown(false);
    };

    const handleClear = () => {
        setQuery('');
        onChange('');
        setOptions([]);
    };

    return (
        <div ref={containerRef} className="relative w-72">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onFocus={() => options.length > 0 && setShowDropdown(true)}
                    placeholder={placeholder}
                    className="w-full pl-9 pr-8 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                {query && (
                    <button
                        onClick={handleClear}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                        <X className="w-4 h-4" />
                    </button>
                )}
            </div>
            {showDropdown && options.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
                    {options.map((opt) => (
                        <button
                            key={opt.stock_code}
                            onClick={() => handleSelect(opt.stock_code, opt.stock_name)}
                            className="w-full px-3 py-2 text-left text-sm hover:bg-blue-50 flex items-center gap-2"
                        >
                            <span className="font-mono text-blue-600 font-medium">{opt.stock_code}</span>
                            <span className="text-gray-700">{opt.stock_name}</span>
                        </button>
                    ))}
                </div>
            )}
            {isLoading && (
                <div className="absolute right-10 top-1/2 -translate-y-1/2">
                    <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                </div>
            )}
        </div>
    );
};
