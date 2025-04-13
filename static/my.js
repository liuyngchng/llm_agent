const chartRules = [
    {pattern: /(趋势|变化|增长|下降)/, type: 'line'},
    {pattern: /(对比|比较|差异|不同)/, type: 'bar'},
    {pattern: /(占比|比例|分布)/, type: 'pie'}
];

function detectChartType(query) {
    return chartRules.find(rule => rule.pattern.test(query))?.type || 'pie';
}
// 判断图表类型
let chartType = detectChartType(query)