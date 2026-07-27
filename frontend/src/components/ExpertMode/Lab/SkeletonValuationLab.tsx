/**
 * 估值实验室骨架屏组件
 * 在数据加载时展示占位动画
 */

export function SkeletonValuationLab() {
    return (
        <div className="space-y-6 animate-pulse">
            {/* Tab bar skeleton */}
            <div className="flex gap-4">
                <div className="h-10 w-48 bg-gray-200 rounded-lg" />
                <div className="h-10 w-56 bg-gray-200 rounded-lg" />
            </div>

            {/* Controls skeleton */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[1, 2, 3].map(i => (
                    <div key={i} className="h-24 bg-gray-200 rounded-xl" />
                ))}
            </div>

            {/* Scenario cards skeleton */}
            <div className="grid grid-cols-3 gap-4">
                {[1, 2, 3].map(i => (
                    <div key={i} className="h-32 bg-gray-200 rounded-xl" />
                ))}
            </div>

            {/* Chart area skeleton */}
            <div className="h-64 bg-gray-200 rounded-xl" />

            {/* Table skeleton */}
            <div className="space-y-3">
                {[1, 2, 3, 4, 5].map(i => (
                    <div key={i} className="h-12 bg-gray-200 rounded-lg" />
                ))}
            </div>
        </div>
    );
}
