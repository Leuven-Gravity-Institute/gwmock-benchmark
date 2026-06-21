// Render interactive Vega-Lite charts for benchmark results. The data is emitted
// inline by `gwmock-benchmark aggregate` as a <script type="application/json"> block;
// this builds one chart per metric next to its <div class="benchmark-charts">.
//
// The x-axis is the waveform model (approximant), not the hardware: each
// backend/method/hardware cell is a coloured scatter point, so models are compared
// side by side and the hardware comparison lives in the colour legend. Models are
// sorted with the best result on the left (per chart: highest throughput, lowest
// wall/memory/loss).
;(function () {
    'use strict'

    var COLD = '#7fcdbb'
    var WARM = '#2c7fb8'
    var SCHEMA = 'https://vega.github.io/schema/vega-lite/v5.json'

    // Per-suite chart definitions: which metric fields become which chart.
    // higherBetter drives the model sort order (best on the left).
    var SUITES = {
        performance: {
            xField: 'approximant',
            charts: [
                {
                    title: 'Throughput',
                    y: 'events / s',
                    cold: 'throughput_cold',
                    warm: 'throughput_warm',
                    higherBetter: true,
                },
                {
                    title: 'Wall time',
                    y: 'seconds',
                    cold: 'wall_cold',
                    warm: 'wall_warm',
                    higherBetter: false,
                },
                {
                    title: 'One-time compile',
                    y: 'seconds',
                    value: 'compile',
                    higherBetter: false,
                },
                {
                    title: 'Peak memory',
                    y: 'GB',
                    value: 'peak_gb',
                    higherBetter: false,
                },
                {
                    title: 'Output data',
                    y: 'GB',
                    value: 'output_gb',
                    higherBetter: false,
                },
            ],
        },
        consistency: {
            xField: 'approximant',
            charts: [
                {
                    title: 'ripple vs LAL — log₁₀ overlap loss',
                    y: 'log₁₀(1 − overlap)',
                    pair: [
                        { key: 'worst_log_loss', name: 'worst' },
                        { key: 'median_log_loss', name: 'median' },
                    ],
                },
            ],
        },
    }

    var X_AXIS = { labelAngle: -30, title: 'waveform model', labelLimit: 280 }

    // Sort the model categories so the best result sits on the left. Aggregating by
    // max (higher-is-better) or min (lower-is-better) picks the headline (warm) value.
    function modelSort(def) {
        return {
            op: def.higherBetter ? 'max' : 'min',
            field: 'value',
            order: def.higherBetter ? 'descending' : 'ascending',
        }
    }

    // Click a cell in the legend to isolate it; everyone else fades.
    function cellHighlight() {
        return {
            name: 'cellSel',
            select: { type: 'point', fields: ['cell'] },
            bind: 'legend',
        }
    }

    function cellTooltip(extra) {
        return [
            { field: 'cell', title: 'cell' },
            { field: 'approximant', title: 'model' },
            { field: 'device' },
            { field: 'version', title: 'gwmock-signal' },
        ].concat(extra || [])
    }

    // Performance throughput/wall: one point per cell, cold and warm by shape.
    function groupedSpec(rows, xField, def) {
        var values = []
        rows.forEach(function (row) {
            ;['cold', 'warm'].forEach(function (phase) {
                values.push({
                    x: row[xField],
                    cell: row.cell,
                    approximant: row.approximant,
                    device: row.device,
                    version: row.version,
                    phase: phase,
                    value: row[def[phase]],
                })
            })
        })
        return {
            $schema: SCHEMA,
            width: 'container',
            height: 340,
            title: def.title + ' — cold vs warm (best on the left)',
            data: { values: values },
            params: [cellHighlight()],
            mark: { type: 'point', filled: true, size: 110, tooltip: true },
            encoding: {
                x: {
                    field: 'x',
                    type: 'nominal',
                    sort: modelSort(def),
                    axis: X_AXIS,
                },
                y: { field: 'value', type: 'quantitative', title: def.y },
                color: { field: 'cell', type: 'nominal', title: null },
                shape: {
                    field: 'phase',
                    title: null,
                    scale: {
                        domain: ['cold', 'warm'],
                        range: ['triangle-up', 'circle'],
                    },
                },
                opacity: {
                    condition: { param: 'cellSel', value: 1 },
                    value: 0.2,
                },
                tooltip: cellTooltip([
                    { field: 'phase' },
                    {
                        field: 'value',
                        type: 'quantitative',
                        format: '.4g',
                        title: def.y,
                    },
                ]),
            },
        }
    }

    // Performance compile/memory/output: one point per cell (single value).
    function singleSpec(rows, xField, def) {
        var values = rows.map(function (row) {
            return {
                x: row[xField],
                cell: row.cell,
                approximant: row.approximant,
                device: row.device,
                version: row.version,
                value: row[def.value],
            }
        })
        return {
            $schema: SCHEMA,
            width: 'container',
            height: 340,
            title: def.title + ' (best on the left)',
            data: { values: values },
            params: [cellHighlight()],
            mark: { type: 'point', filled: true, size: 120, tooltip: true },
            encoding: {
                x: {
                    field: 'x',
                    type: 'nominal',
                    sort: modelSort(def),
                    axis: X_AXIS,
                },
                y: { field: 'value', type: 'quantitative', title: def.y },
                color: { field: 'cell', type: 'nominal', title: null },
                opacity: {
                    condition: { param: 'cellSel', value: 1 },
                    value: 0.2,
                },
                tooltip: cellTooltip([
                    {
                        field: 'value',
                        type: 'quantitative',
                        format: '.5g',
                        title: def.y,
                    },
                ]),
            },
        }
    }

    // Consistency: worst- and median-case log overlap loss per model. Lower (more
    // negative) is better, so models sort by their worst case ascending — best on left.
    function pairSpec(rows, xField, def) {
        var values = []
        rows.forEach(function (row) {
            def.pair.forEach(function (metric) {
                values.push({
                    x: row[xField],
                    approximant: row.approximant,
                    device: row.device,
                    version: row.version,
                    kind: metric.name,
                    value: row[metric.key],
                })
            })
        })
        return {
            $schema: SCHEMA,
            width: 'container',
            height: 340,
            title: def.title + ' — lower is better (best on the left)',
            data: { values: values },
            mark: { type: 'point', filled: true, size: 140, tooltip: true },
            encoding: {
                x: {
                    field: 'x',
                    type: 'nominal',
                    sort: { op: 'max', field: 'value', order: 'ascending' },
                    axis: X_AXIS,
                },
                y: { field: 'value', type: 'quantitative', title: def.y },
                color: {
                    field: 'kind',
                    title: null,
                    scale: { domain: ['worst', 'median'], range: [WARM, COLD] },
                },
                shape: {
                    field: 'kind',
                    title: null,
                    scale: {
                        domain: ['worst', 'median'],
                        range: ['circle', 'diamond'],
                    },
                },
                tooltip: [
                    { field: 'approximant', title: 'model' },
                    { field: 'version', title: 'gwmock-signal' },
                    { field: 'device' },
                    { field: 'kind' },
                    {
                        field: 'value',
                        type: 'quantitative',
                        format: '.2f',
                        title: def.y,
                    },
                ],
            },
        }
    }

    function specFor(rows, xField, def) {
        if (def.pair) return pairSpec(rows, xField, def)
        if (def.value) return singleSpec(rows, xField, def)
        return groupedSpec(rows, xField, def)
    }

    // Charts rendered on the page, kept so a palette toggle can re-embed them.
    var rendered = []
    var retryTimer
    var renderSeq = 0
    var PENDING_TIMEOUT_MS = 15000
    var EMBED_TIMEOUT_MS = 20000
    var resizeObserver =
        typeof ResizeObserver === 'undefined'
            ? null
            : new ResizeObserver(function () {
                  scheduleSweep(50)
              })

    // Material/zensical sets data-md-color-scheme="slate" on <body> for dark mode.
    // Override only the chrome (text, axes, legend, grid); data colours are shared.
    function themeConfig() {
        var dark =
            document.body.getAttribute('data-md-color-scheme') === 'slate'
        if (!dark) return { background: 'transparent' }
        var fg = '#e3e3e3'
        var muted = '#9aa0a6'
        var grid = '#3a3f44'
        return {
            background: 'transparent',
            title: { color: fg, subtitleColor: muted },
            axis: {
                labelColor: muted,
                titleColor: fg,
                gridColor: grid,
                domainColor: grid,
                tickColor: grid,
            },
            legend: { labelColor: muted, titleColor: fg },
            view: { stroke: 'transparent' },
        }
    }

    function scheduleSweep(delay) {
        if (retryTimer) return
        retryTimer = setTimeout(function () {
            retryTimer = null
            sweepUntilReady()
        }, delay || 50)
    }

    function afterLayout(callback) {
        if (typeof requestAnimationFrame !== 'undefined') {
            requestAnimationFrame(function () {
                requestAnimationFrame(callback)
            })
            return
        }
        setTimeout(callback, 50)
    }

    function chartTargetsReady(charts) {
        return charts.every(function (chart) {
            return chart.div.getBoundingClientRect().width > 0
        })
    }

    function waitForChartTargets(charts, attempt) {
        attempt = attempt || 0
        return new Promise(function (resolve, reject) {
            afterLayout(function () {
                if (chartTargetsReady(charts)) {
                    resolve()
                    return
                }
                if (attempt >= 120) {
                    reject(new Error('chart container never became visible'))
                    return
                }
                waitForChartTargets(charts, attempt + 1).then(resolve, reject)
            })
        })
    }

    function chartSvgReady(chart) {
        var svg = chart.div.querySelector('svg')
        if (!svg) return false
        var box = svg.getBoundingClientRect()
        return box.width > 0 && box.height > 0
    }

    function renderedChartsReady(charts) {
        return charts.every(chartSvgReady)
    }

    function waitForRenderedCharts(charts, attempt) {
        attempt = attempt || 0
        return new Promise(function (resolve, reject) {
            afterLayout(function () {
                if (renderedChartsReady(charts)) {
                    resolve()
                    return
                }
                if (attempt >= 120) {
                    reject(new Error('chart rendered with zero size'))
                    return
                }
                waitForRenderedCharts(charts, attempt + 1).then(resolve, reject)
            })
        })
    }

    function withTimeout(promise, ms, message) {
        var timer
        var timeout = new Promise(function (_, reject) {
            timer = setTimeout(function () {
                reject(new Error(message))
            }, ms)
        })
        return Promise.race([promise, timeout]).then(
            function (value) {
                clearTimeout(timer)
                return value
            },
            function (error) {
                clearTimeout(timer)
                throw error
            }
        )
    }

    function embed(chart) {
        // Tear down a prior render so a theme toggle replaces rather than stacks.
        if (chart.view && chart.view.finalize) chart.view.finalize()
        chart.div.innerHTML = ''
        return window
            .vegaEmbed(chart.div, chart.spec, {
                actions: {
                    export: true,
                    source: false,
                    compiled: false,
                    editor: false,
                },
                renderer: 'svg',
                config: themeConfig(),
            })
            .then(function (result) {
                chart.view = result.view
                return chart
            })
    }

    function clearCharts(charts) {
        charts.forEach(function (chart) {
            if (chart.view && chart.view.finalize) chart.view.finalize()
        })
        rendered = rendered.filter(function (chart) {
            return charts.indexOf(chart) === -1
        })
    }

    function observeContainer(container) {
        if (!resizeObserver || container.dataset.benchmarkObserved === 'true') {
            return
        }
        resizeObserver.observe(container)
        container.dataset.benchmarkObserved = 'true'
    }

    function pendingIsFresh(container) {
        var started = Number(container.dataset.benchmarkPendingAt || 0)
        return started && Date.now() - started < PENDING_TIMEOUT_MS
    }

    function resetContainer(container) {
        delete container.dataset.benchmarkPending
        delete container.dataset.benchmarkPendingAt
        delete container.dataset.benchmarkRendered
        delete container.dataset.benchmarkRenderId
        container.innerHTML = ''
    }

    // Render one container's charts, once. Returns false to signal "try again later"
    // when Vega has not loaded yet or the container has no width (layout not settled -
    // a `width: 'container'` spec would otherwise measure 0 and render invisibly).
    function renderContainer(container) {
        if (container.dataset.benchmarkRendered === 'true') return true
        if (container.dataset.benchmarkPending === 'true') {
            if (pendingIsFresh(container)) return true
            resetContainer(container)
        }
        observeContainer(container)
        var group = container.getAttribute('data-group')
        var config = SUITES[container.getAttribute('data-suite')]
        var script = document.querySelector(
            'script.benchmark-chart-data[data-group="' + group + '"]'
        )
        if (!config) return true // nothing renderable here
        if (!script) return false
        if (typeof window.vegaEmbed === 'undefined') return false
        if (container.getBoundingClientRect().width === 0) return false

        var rows
        try {
            rows = JSON.parse(script.textContent)
        } catch (error) {
            return true
        }
        var renderId = String(++renderSeq)
        container.dataset.benchmarkPending = 'true'
        container.dataset.benchmarkPendingAt = String(Date.now())
        container.dataset.benchmarkRenderId = renderId
        container.innerHTML = ''
        var charts = []
        config.charts.forEach(function (def) {
            var div = document.createElement('div')
            div.className = 'benchmark-chart'
            container.appendChild(div)
            var chart = { div: div, spec: specFor(rows, config.xField, def) }
            charts.push(chart)
        })
        waitForChartTargets(charts)
            .then(function () {
                return withTimeout(
                    Promise.all(charts.map(embed)),
                    EMBED_TIMEOUT_MS,
                    'chart embedding timed out'
                )
            })
            .then(function () {
                return withTimeout(
                    waitForRenderedCharts(charts),
                    EMBED_TIMEOUT_MS,
                    'chart rendered with zero size'
                )
            })
            .then(function () {
                if (container.dataset.benchmarkRenderId !== renderId) {
                    clearCharts(charts)
                    return
                }
                delete container.dataset.benchmarkPending
                delete container.dataset.benchmarkPendingAt
                delete container.dataset.benchmarkRenderId
                if (!container.isConnected) {
                    clearCharts(charts)
                    return
                }
                rendered = rendered.concat(charts)
                container.dataset.benchmarkRendered = 'true'
            })
            .catch(function () {
                clearCharts(charts)
                if (container.dataset.benchmarkRenderId === renderId) {
                    resetContainer(container)
                }
                scheduleSweep(300)
            })
        return true
    }

    // Drop charts whose container was swapped out (instant navigation), finalizing
    // their Vega views so they don't leak across navigations.
    function prune() {
        rendered = rendered.filter(function (chart) {
            if (chart.div.isConnected) return true
            if (chart.view && chart.view.finalize) chart.view.finalize()
            return false
        })
    }

    // Render every container on the page; returns true if any still needs a retry.
    function sweep() {
        prune()
        var pending = false
        document
            .querySelectorAll('.benchmark-charts')
            .forEach(function (container) {
                if (!renderContainer(container)) pending = true
            })
        return pending
    }

    function sweepUntilReady(attempt) {
        attempt = attempt || 0
        if (sweep() && attempt < 120) {
            setTimeout(function () {
                sweepUntilReady(attempt + 1)
            }, 250)
        }
    }

    function hasUnrenderedContainers() {
        return Array.prototype.some.call(
            document.querySelectorAll('.benchmark-charts'),
            function (container) {
                if (container.dataset.benchmarkRendered === 'true') {
                    return false
                }
                return (
                    container.dataset.benchmarkPending !== 'true' ||
                    !pendingIsFresh(container)
                )
            }
        )
    }

    // Re-embed live charts whenever the colour scheme toggles.
    function watchTheme() {
        if (typeof MutationObserver === 'undefined') return
        new MutationObserver(function (mutations) {
            if (
                mutations.some(
                    (m) => m.attributeName === 'data-md-color-scheme'
                )
            ) {
                prune()
                rendered.forEach(embed)
            }
        }).observe(document.body, {
            attributes: true,
            attributeFilter: ['data-md-color-scheme'],
        })
    }

    function sweepAfterNavigation() {
        sweepUntilReady()
        setTimeout(sweepUntilReady, 50)
        setTimeout(sweepUntilReady, 150)
        setTimeout(sweepUntilReady, 500)
        setTimeout(sweepUntilReady, 1000)
    }

    // Instant navigation swaps the page body in after load (sometimes replacing a
    // container we already rendered into with a fresh, empty one). Watch the document
    // root rather than the current body, because instant navigation can replace the
    // body node after this script has subscribed.
    function watchBody() {
        if (typeof MutationObserver === 'undefined') return
        var timer
        new MutationObserver(function () {
            clearTimeout(timer)
            timer = setTimeout(sweepAfterNavigation, 50)
        }).observe(document.documentElement || document.body, {
            childList: true,
            subtree: true,
        })
    }

    // A light safety net for instant navigation: if the URL changed before the new
    // page fragment arrived, no mutation or document$ callback may line up with the
    // eventual chart container. Poll only while there is an unrendered chart target.
    function watchChartArrival() {
        setInterval(function () {
            if (hasUnrenderedContainers()) sweepUntilReady()
        }, 500)
    }

    function watchLocation() {
        var href = window.location.href
        setInterval(function () {
            if (window.location.href === href) return
            href = window.location.href
            sweepAfterNavigation()
        }, 100)
    }

    function patchHistory() {
        ;['pushState', 'replaceState'].forEach(function (name) {
            var original = window.history && window.history[name]
            if (!original || original.benchmarkChartsPatched) return
            var patched = function () {
                var result = original.apply(this, arguments)
                sweepAfterNavigation()
                return result
            }
            patched.benchmarkChartsPatched = true
            window.history[name] = patched
        })
    }

    function watchPageReadiness() {
        window.addEventListener('load', sweepAfterNavigation)
        window.addEventListener('pageshow', sweepAfterNavigation)
        window.addEventListener('popstate', sweepAfterNavigation)
        window.addEventListener('hashchange', sweepAfterNavigation)
        window.addEventListener('resize', function () {
            scheduleSweep(100)
        })
    }

    function start() {
        patchHistory()
        sweepAfterNavigation()
        watchTheme()
        watchBody()
        watchChartArrival()
        watchLocation()
        watchPageReadiness()
    }

    // Re-render on each instant navigation, and once for the initial page (covering a
    // document$ first-emission that fired before this script subscribed). renderContainer
    // is keyed per container, so overlapping triggers never double-render.
    if (typeof window.document$ !== 'undefined' && window.document$.subscribe) {
        window.document$.subscribe(sweepAfterNavigation)
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start)
    } else {
        start()
    }
})()
