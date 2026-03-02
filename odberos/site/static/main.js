document.addEventListener('DOMContentLoaded', function() {
    const telefonInput = document.querySelector('#telefon');
    if (!telefonInput) return;

    // Vždy jen číslice – backend očekává prázdno nebo 9 číslic
    telefonInput.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 9) value = value.slice(0, 9);
        e.target.value = value;
    });

    // Skryté pole +420 jen pro reklamace (ne pro odběry – tam by to dublovalo a kolidovalo)
    telefonInput.addEventListener('blur', function() {
        const form = telefonInput.closest('form');
        if (!form || form.id === 'odberForm') return;
        const digits = (telefonInput.value || '').replace(/\D/g, '');
        form.querySelectorAll('input[type=hidden][name=telefon]').forEach(function(el) { el.remove(); });
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'telefon';
        hiddenInput.value = digits;
        form.appendChild(hiddenInput);
    });
});