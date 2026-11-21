## Period views Day / Week / Month / Year (js/periods.js). Hidden while Live! is active.
#set $periodTextKeys = ['Current', 'Today', 'rolling', 'Previous period', 'Next period', 'Select period', 'Loading', 'No data available', 'Data not yet available', 'Incomplete data', 'Generation failed', 'Regeneration required', 'History is being built', 'provisional', 'Data as of', 'min', 'avg', 'max', 'Sum', 'Count', 'First', 'Last', 'Vector direction']
<template id="periodTexts">
    #for $key in $periodTextKeys
    <span data-key="$key">$gettext($key)</span>
    #end for
</template>
<style>
    .periodPickerPanel { top: 100%; left: 0; min-width: 18rem; max-width: 22rem; z-index: 1050; }
    .periodPickGrid { display: grid; gap: 2px; }
    .periodPickDays { grid-template-columns: repeat(7, 1fr); }
    .periodPickWeek { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(7, 1fr); }
    .periodPickCells { grid-template-columns: repeat(3, 1fr); }
    .periodPickWeekday { text-align: center; }
    .periodPickCell { padding: 0.15rem 0.25rem; }
    .periodPickOutside { opacity: 0.55; }
    .periodPickCell:disabled { opacity: 0.4; }
    .periodPickCell.periodState-running:not(.btn-primary) { font-weight: bold; }
    .periodPickCell.periodState-gaps:not(.btn-primary) { background: repeating-linear-gradient(135deg, transparent 0 4px, rgba(255, 193, 7, 0.35) 4px 6px); }
    .periodPickCell.periodState-error, .periodPickCell.periodState-incompatible { text-decoration: line-through; }
    .periodPickSwatch { display: inline-block; width: 0.8em; height: 0.8em; margin-right: 0.25em; border: 1px solid #adb5bd; vertical-align: middle; }
    .periodPickSwatch.periodState-gaps { background: repeating-linear-gradient(135deg, transparent 0 2px, rgba(255, 193, 7, 0.6) 2px 3px); }
    .periodPickSwatch.periodState-pending { background: #e9ecef; }
    .periodPickSwatch.periodState-error, .periodPickSwatch.periodState-incompatible { background: #f8d7da; }
    .periodPickSwatch.periodState-nodata { background: transparent; }
</style>
<div id="periodView" class="d-none" aria-live="polite">
    <div id="periodToolbar" class="d-flex flex-wrap align-items-center gap-1 my-1">
        <button type="button" id="periodPrev" class="btn btn-light primaryLight" title="$gettext('Previous period')" aria-label="$gettext('Previous period')"><i class="bi bi-chevron-left"></i></button>
        <button type="button" id="periodPicker" class="btn btn-light primaryLight" title="$gettext('Select period')" aria-label="$gettext('Select period')"><i class="bi bi-calendar3"></i></button>
        <button type="button" id="periodNext" class="btn btn-light primaryLight" title="$gettext('Next period')" aria-label="$gettext('Next period')"><i class="bi bi-chevron-right"></i></button>
        <button type="button" id="periodCurrent" class="btn btn-light primaryLight d-none">$gettext('Current')</button>
        <button type="button" id="periodToday" class="btn btn-light primaryLight d-none">$gettext('Today')</button>
        <h2 id="periodTitle" class="h5 mb-0 ms-2"></h2>
        <span id="periodRolling" class="badge text-bg-secondary d-none">$gettext('rolling')</span>
        <small id="periodDataState" class="text-muted ms-auto"></small>
    </div>
    <div id="periodStatus" class="alert py-1 px-2 my-1 periodStatus d-none" role="status"></div>
    <div id="periodCharts" class="row"></div>
</div>
<script type="text/javascript">
#raw
    // Avoid flashing the Live charts when the page is opened with a period deep link.
    if (/^#(day|week|month|year)(\/|$)/.test(location.hash)) {
        document.getElementById("liveView").classList.add("d-none");
        document.getElementById("periodView").classList.remove("d-none");
    }
#end raw
</script>
