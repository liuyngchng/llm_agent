const outputEl = document.getElementById('stream_output');
const startBtn = document.getElementById('startBtn');
let eventSource = null;
let currentQuery = '';
const chartRules = [
    {pattern: /(趋势|变化|增长|下降)/, type: 'line'},
    {pattern: /(对比|比较|差异|不同|排名|排序)/, type: 'bar'},
    {pattern: /(占比|比例|分布)/, type: 'pie'}
];

function detectChartType(query) {
    return chartRules.find(rule => rule.pattern.test(query))?.type || 'pie';
}

startBtn.addEventListener('click', () => {
    if (eventSource) eventSource.close();
    outputEl.innerHTML = '<div class="empty-state"><p>正在处理您的查询，请稍候...</p></div>';
    currentQuery = document.getElementById('dialog').value;
    const query = encodeURIComponent(currentQuery);
    const uid = encodeURIComponent(document.getElementById('uid').value);

    eventSource = new EventSource(`/stream?t=${Date.now()}&q=${query}&uid=${uid}`);
    eventSource.onmessage = (event) => {
        const lastChild = outputEl.lastElementChild;
        if (lastChild && (lastChild.textContent || '').includes('...')) {
            outputEl.removeChild(lastChild);
        }
        try {
            const { data_type, data } = JSON.parse(event.data);
            console.log("switch_case, data_type="+ data_type + ", data=" + data)
            switch(data_type) {
                case 'txt':
                handleTxtData(data);
                break;
            case 'html':
                handleHtmlData(data);
                break;
            case 'chart_js':
                handleChartData(data, currentQuery);
                break;
            case 'msg':
                console.log("switch_msg, data_type="+ data_type + ", data=" + data)
                handleMsgData(data);
                break;
            default:
                console.warn('未知数据类型:', data_type);
            }
        } catch (e) {
            console.error('数据解析失败', e);
            const fallback = document.createElement('div');
            fallback.className = 'response-card';
            fallback.innerHTML = `<div class="warning-message">数据解析错误: ${e.message}</div>`;
            outputEl.appendChild(fallback);
        }
    };
    eventSource.onerror = handleSSEError;
});

function handleTxtData(data) {
    const pre = document.createElement('pre');
    pre.style.whiteSpace = 'pre-wrap';
    pre.textContent = data;
    outputEl.appendChild(pre);
}

function handleHtmlData(data) {
    const html_container = document.createElement('div');
    html_container.className = 'response-card';
    html_container.innerHTML = data;
    outputEl.appendChild(html_container);
}

function handleChartData(data, query) {
    const chart_container = document.createElement('div');
    chart_container.className = 'chart-container';
    outputEl.appendChild(chart_container);
    const canvas = document.createElement('canvas');
    chart_container.appendChild(canvas);
    const chartType = detectChartType(query);

    const chartConfig = {
        type: chartType,
        data: {
            labels: data.chart.labels,
            datasets: [{
                label: data.chart.title || '数据',
                data: data.chart.values,
                backgroundColor: [
                    'rgba(75, 108, 183, 0.7)',
                    'rgba(46, 204, 113, 0.7)',
                    'rgba(155, 89, 182, 0.7)',
                    'rgba(241, 196, 15, 0.7)',
                    'rgba(230, 126, 34, 0.7)'
                ],
                borderColor: 'white',
                borderWidth: 2,
                ...(chartType === 'line' && {
                    fill: false,
                    tension: 0.4,
                    borderColor: '#4b6cb7'
                })
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: chartType === 'pie' ? 'right' : 'top'
                },
                title: {
                    display: true,
                    text: data.chart.title,
                    font: { size: 18 }
                }
            },
            ...(chartType !== 'pie' && {
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: '类别'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: data.chart.unit ? `数值 (${data.chart.unit})` : '数值'
                        },
                        beginAtZero: true
                    }
                }
            })
        }
    };

    new Chart(canvas, chartConfig);
}

function handleMsgData(data) {
    if (data.cur_page !== undefined) {
        document.getElementById('cur_page').value = data.cur_page;
    }
    if (data.total_page !== undefined) {
        document.getElementById('total_page').value = data.total_page;
    }
    if (data.total_count !== undefined) {
        document.getElementById('total_count').value = data.total_count;
    }
}

window.loadNextPage = function(e) {
    e.preventDefault();
    const curPage = parseInt(document.getElementById('cur_page').value || '0');
    const totalPage = parseInt(document.getElementById('total_page').value || '0');
    if (curPage >= totalPage) {
        alert("已经是最后一页了");
        return;
    }
    const nextPage = curPage + 1;
    const query = encodeURIComponent(document.getElementById('dialog').value);
    const uid = encodeURIComponent(document.getElementById('uid').value);
    if (eventSource) eventSource.close();
    outputEl.innerHTML = `<pre style="white-space: pre-wrap;">${currentQuery}, 翻页到第 ${nextPage}页/总共 ${totalPage} 页</pre>`;
    uri = `/stream?t=${Date.now()}&uid=${uid}&page=${nextPage}`
    eventSource = new EventSource(uri);
    console.log("new_event_source_uri=" + uri)
    eventSource.onmessage = handleSSEMessage;
    eventSource.onerror = handleSSEError;
};

function handleSSEError(event) {
    console.error("EventSource error:", event);
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}