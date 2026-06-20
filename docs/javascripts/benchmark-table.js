// Progressive enhancement for benchmark result tables: click a header to sort
// (numeric-aware), type in the box to filter rows. No external dependencies.
;(function () {
    'use strict'

    function isNumeric(value) {
        return value !== '' && !isNaN(parseFloat(value))
    }

    function enhance(table) {
        if (table.dataset.enhanced === 'true') return
        table.dataset.enhanced = 'true'

        var thead = table.tHead
        var tbody = table.tBodies[0]
        if (!thead || !tbody) return
        var headers = Array.prototype.slice.call(thead.rows[0].cells)
        var rows = function () {
            return Array.prototype.slice.call(tbody.rows)
        }

        // Wrap the table: a search box on top, the table in a horizontal scroller.
        var wrap = document.createElement('div')
        wrap.className = 'benchmark-table-wrap'
        table.parentNode.insertBefore(wrap, table)

        var search = document.createElement('input')
        search.type = 'search'
        search.className = 'benchmark-table-search'
        search.placeholder = 'Search / filter…'
        search.setAttribute('aria-label', 'Search table')

        var scroller = document.createElement('div')
        scroller.className = 'benchmark-table-scroll'

        wrap.appendChild(search)
        wrap.appendChild(scroller)
        scroller.appendChild(table)

        search.addEventListener('input', function () {
            var query = search.value.trim().toLowerCase()
            rows().forEach(function (row) {
                var hit =
                    query === '' ||
                    row.textContent.toLowerCase().indexOf(query) !== -1
                row.style.display = hit ? '' : 'none'
            })
        })

        headers.forEach(function (th, index) {
            th.classList.add('sortable')
            th.tabIndex = 0
            var sort = function () {
                var numeric = rows().every(function (row) {
                    return isNumeric(row.cells[index].textContent.trim())
                })
                var ascending = th.dataset.sort !== 'asc'
                headers.forEach(function (other) {
                    delete other.dataset.sort
                })
                th.dataset.sort = ascending ? 'asc' : 'desc'
                rows()
                    .sort(function (a, b) {
                        var av = a.cells[index].textContent.trim()
                        var bv = b.cells[index].textContent.trim()
                        var cmp = numeric
                            ? parseFloat(av) - parseFloat(bv)
                            : av.localeCompare(bv)
                        return ascending ? cmp : -cmp
                    })
                    .forEach(function (row) {
                        tbody.appendChild(row)
                    })
            }
            th.addEventListener('click', sort)
            th.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    sort()
                }
            })
        })
    }

    function init() {
        document.querySelectorAll('table.benchmark-table').forEach(enhance)
    }

    // Material/zensical instant navigation swaps content without a full reload;
    // re-run on each page via document$ when available, else on initial load.
    if (typeof window.document$ !== 'undefined' && window.document$.subscribe) {
        window.document$.subscribe(init)
    } else {
        document.addEventListener('DOMContentLoaded', init)
    }
})()
