(function () {
    function parseChartData(el) {
        if (!el) return null;
        try {
            return JSON.parse(el.dataset.chart || '{}');
        } catch (error) {
            return null;
        }
    }

    function palette(type) {
        if (type === 'doughnut') {
            return [
                'rgba(37, 99, 235, 0.85)',
                'rgba(14, 165, 233, 0.8)',
                'rgba(244, 114, 182, 0.8)',
                'rgba(245, 158, 11, 0.8)',
            ];
        }
        return 'rgba(37, 99, 235, 0.75)';
    }

    function renderChart(canvas) {
        const data = parseChartData(canvas);
        if (!canvas || !data || !data.labels || !data.values) return;

        const chartType = canvas.dataset.chartType || 'bar';
        const label = canvas.dataset.chartLabel || 'Value';
        const colors = palette(chartType);

        new Chart(canvas, {
            type: chartType,
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: label,
                        data: data.values,
                        borderRadius: chartType === 'bar' ? 8 : 0,
                        backgroundColor: colors,
                        borderColor: chartType === 'line' ? 'rgba(37, 99, 235, 1)' : colors,
                        borderWidth: 2,
                        fill: chartType === 'line',
                        tension: chartType === 'line' ? 0.35 : 0,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: chartType !== 'bar' },
                },
                scales: chartType === 'doughnut'
                    ? {}
                    : {
                          y: { beginAtZero: true },
                      },
            },
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('canvas[data-chart]').forEach((canvas) => renderChart(canvas));
    });
})();
