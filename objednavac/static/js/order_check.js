/**
 * Kontrola objednávky – obsluha vstupu pro sken (množství*EAN).
 * Debounce zamezí dvojímu odeslání při rychlém skenování.
 */
function orderCheckInit(options) {
    var orderId = options.orderId;
    var scanInput = options.scanInput;
    var feedback = options.feedback;
    var debounceMs = options.debounceMs || 400;
    var lastSubmit = 0;

    function submitScan(val) {
        val = (val || '').trim();
        if (!val) return;
        var now = Date.now();
        if (now - lastSubmit < debounceMs) return;
        lastSubmit = now;

        if (feedback) feedback.textContent = 'Odesílám…';
        fetch('/warehouse/order/' + orderId + '/check/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
            body: 'scan=' + encodeURIComponent(val)
        }).then(function(r) { return r.json(); }).then(function(data) {
            if (data.ok) {
                if (feedback) {
                    feedback.textContent = data.result === 'correct' ? 'Správně' : 'Nesprávně';
                    feedback.className = 'scan-feedback ' + (data.result === 'correct' ? 'feedback-correct' : 'feedback-incorrect');
                }
                var row = document.getElementById('check-row-' + data.order_item_id);
                if (row) {
                    row.className = data.result === 'correct' ? 'item-check-correct' : 'item-check-incorrect';
                    var td = row.querySelector('.check-result-cell');
                    if (td) td.textContent = data.scanned_quantity + ' skenováno → ' + (data.result === 'correct' ? 'Správně' : 'Nesprávně');
                }
                if (scanInput) scanInput.value = '';
                if (data.all_checked && feedback) {
                    feedback.textContent += '. ' + (data.all_correct ? 'Objednávka zkontrolována.' : 'Zjištěna chyba.');
                }
            } else {
                if (feedback) {
                    feedback.textContent = data.error || 'Chyba';
                    feedback.className = 'scan-feedback feedback-error';
                }
            }
        }).catch(function() {
            if (feedback) {
                feedback.textContent = 'Chyba spojení';
                feedback.className = 'scan-feedback feedback-error';
            }
        });
    }

    if (scanInput) {
        scanInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitScan(scanInput.value);
            }
        });
    }
}
