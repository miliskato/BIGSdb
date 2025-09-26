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

function prepareBatchSubmit() {
    var form = document.getElementById('isolateSubmissionsForm');
    if (!form) return false;

    // Add validation flag
    var validateInput = document.createElement('input');
    validateInput.type = 'hidden';
    validateInput.name = 'validate_submission';
    validateInput.value = '1';
    form.appendChild(validateInput);

    // Set status to 'closed' for validation
    var statusInput = document.createElement('input');
    statusInput.type = 'hidden';
    statusInput.name = 'status';
    statusInput.value = 'closed';
    form.appendChild(statusInput);

    // Get all submission IDs from hidden inputs
    var hiddenInputs = document.getElementsByClassName('batch_submission_id');

    // Create submission_ids inputs for validation
    Array.from(hiddenInputs).forEach(function(input) {
        var submissionInput = document.createElement('input');
        submissionInput.type = 'hidden';
        submissionInput.name = 'submission_ids[]';
        submissionInput.value = input.value;
        form.appendChild(submissionInput);
    });

    // Check all checkboxes for UI feedback
    var checkboxes = document.getElementsByName('selected_submissions[]');
    for(var i = 0; i < checkboxes.length; i++) {
        checkboxes[i].checked = true;
    }

    return true;
}
