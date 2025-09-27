function toggleCheckboxes(formId) {
    const form = document.getElementById(formId);
    if (!form) return;

    const checkboxes = form.getElementsByTagName('input');
    const checkAllBtn = document.getElementById(formId + '_checkAll');
    const isChecked = checkAllBtn.getAttribute('data-checked') !== 'true';

    for (let i = 0; i < checkboxes.length; i++) {
        if (checkboxes[i].type === 'checkbox') {
            checkboxes[i].checked = isChecked;
        }
    }

    checkAllBtn.setAttribute('data-checked', isChecked);
    checkAllBtn.innerText = isChecked ? 'Uncheck All' : 'Check All';
}

function toggleCheckboxesByQuality(formId, quality) {
    const form = document.getElementById(formId);
    if (!form) return;

    const checkQualityBtn = document.getElementById(formId + '_check' + quality.charAt(0).toUpperCase() + quality.slice(1));
    const isChecked = checkQualityBtn.getAttribute('data-checked') !== 'true';

    const rows = form.getElementsByTagName('tr');
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const checkbox = row.querySelector('input[type="checkbox"]');
        const qualityCell = row.querySelector('td:nth-child(6)'); // Quality is in the 6th column

        if (checkbox && qualityCell && qualityCell.textContent.trim().toLowerCase() === quality.toLowerCase()) {
            checkbox.checked = isChecked;
        }
    }

    checkQualityBtn.setAttribute('data-checked', isChecked);
    checkQualityBtn.innerText = isChecked ? 'Uncheck ' + quality.charAt(0).toUpperCase() + quality.slice(1) + ' Quality' :
                                          'Check ' + quality.charAt(0).toUpperCase() + quality.slice(1) + ' Quality';
}

function applyStatusToSelected() {
    const form = document.getElementById('isolateSubmissionsForm');
    if (!form) return;

    const statusDropdown = document.getElementById('statusDropdown');
    if (!statusDropdown.value) {
        alert('Please select a status');
        return;
    }

    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    let anyChecked = false;

    // Add hidden input for bulk status update
    const statusInput = document.createElement('input');
    statusInput.type = 'hidden';
    statusInput.name = 'bulk_status';
    statusInput.value = statusDropdown.value;
    form.appendChild(statusInput);

    // Collect selected submission IDs
    checkboxes.forEach(checkbox => {
        if (checkbox.checked) {
            anyChecked = true;
            const submissionIdInput = document.createElement('input');
            submissionIdInput.type = 'hidden';
            submissionIdInput.name = 'submission_ids[]';
            submissionIdInput.value = checkbox.value;
            form.appendChild(submissionIdInput);
        }
    });

    if (!anyChecked) {
        alert('Please select at least one submission');
        return;
    }

    form.submit();
}

function validateAndSubmit() {
    const form = document.getElementById('isolateSubmissionsForm');
    if (!form) return false;

    const statusDropdown = document.getElementById('statusDropdown');
    if (!statusDropdown.value) {
        alert('Please select a status');
        return false;
    }

    const checkboxes = form.querySelectorAll('input[type="checkbox"]:checked');
    if (checkboxes.length === 0) {
        alert('Please select at least one submission');
        return false;
    }

    return true;
}


