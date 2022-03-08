/* SUCCESS OR ERROR MESSAGE */
const success_modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('success-modal')),
        success_icon = document.getElementById('success-icon'),
        success_title = document.getElementById('success-title');
function modalResult(error_message = null, success_message = null) {
    success_modal.show();
    success_title.innerHTML = error_message || success_message || 'Saved successfully!';
    if (error_message) {
        success_icon.classList.remove('bi-check2-circle');
        success_icon.classList.remove('text-danger');
        success_icon.classList.add('bi-x-circle');
        success_icon.classList.add('text-danger');
    } else {
        success_icon.classList.add('bi-check2-circle');
        success_icon.classList.add('text-success');
        success_icon.classList.remove('bi-x-circle');
        success_icon.classList.remove('text-danger');
        setTimeout(function() {
            success_modal.hide();
        }, 1500);
    }
    // loadData(true);
}

/* AJAX DATA LOADING */
const servicePool = document.getElementById('service-pool'),
        countdown = document.getElementById('countdown'),
        REFRESH_INTERVAL = 5; // In seconds
let left4refresh = 0;
function addService(id, name, running, blockednow, blocked24, lastblock) {
    let is_running = !(running === 'false' || running == 0 || false);
    servicePool.innerHTML +=
        '            <div class="col-md-4">\n' +
        '                <div class="card my-3">\n' +
        '                    <div class="card-header d-flex justify-content-between align-items-center"><div>\n' +
        '                        <h3 class="card-title m-0">' + name + '</h3>\n' +
        '                        <span class="text-' + (is_running ? 'success' : 'danger') + '" style="margin-left: -4px"><i class="bi bi-' + (is_running ? 'play' : 'pause') + '-fill me-1"></i>' + (is_running ? 'Running' : 'Paused') + '</h3>\n' +
        '                    </div><div class="btn-group-vertical" role="group" aria-label="Service options"><a class="btn btn-warning" href="javascript:playPause(' + id + ')"><i class="bi bi-' + (is_running ? 'pause' : 'play') + '-fill" style="margin: 0px -5px"></i></a><a class="btn btn-danger" data-bs-toggle="modal" data-bs-target="#confirm-delete" onclick="setForDeletion(' + id + ')"><i class="bi bi-trash3-fill" style="margin: 0px -5px"></i></a></div></div>\n' +
        '                    <div class="card-body">\n' +
        '                        <p class="card-text mb-0"><i class="bi bi-circle-fill me-2 text-' + (blockednow == 0 ? 'success' : 'danger')  + '"></i>' + (blockednow || 'No') + ' currently blocked IP' + (blockednow == 1 ? '' : 's') + '</p>\n' +
        '                        <p class="text-muted pt-0 ms-4">' + (lastblock ? ('Last block ' + lastblock) : 'No IPs blocked yet') + '</p>\n' +
        '                        <p class="card-text"><i class="bi bi-circle-fill me-2 text-' + (blocked24 == 0 ? 'success' : 'danger')  + '"></i>' + (blocked24 || 'No') + ' blocked IP' + (blocked24 == 1 ? '' : 's') + ' in the last 24h</p>\n' +
        '                    </div>\n' +
        '                    <div class="btn-group rounded-bottom bg-primary" style="margin-bottom: -2px">\n' +
        '                        <a class="btn btn-primary rounded-bottom rounded-0" data-bs-toggle="modal" data-bs-target="#smodal" onclick="loadServiceSettings(' + id + ')"><i class="bi bi-gear-fill me-2"></i>Settings</a>\n' +
        '                        <a class="btn btn-primary rounded-bottom rounded-0" href="service/' + id + '"><i class="bi bi-list me-2"></i>Blocked IPs</a>\n' +
        '                    </div>\n' +
        '                </div>\n' +
        '            </div>'
}
function loadData(manual=false) {
    if (manual || left4refresh == 0) {
        $.ajax({
            dataType: "json",
            url: "./API/services",
            type: 'GET',
            success: function(data) {
                servicePool.innerHTML = '';
                for (let i = 0; i < data.length; i++)
                    addService(data[i]['id'], data[i]['name'], !data[i]['stopped'], data[i]['blocked_now'], data[i]['blocked_24h'], data[i]['last_blocked']);
                if (data.length == 0)
                    servicePool.innerHTML = '<div class="text-center my-5 text-muted">No services have been created yet</div>';
                left4refresh = REFRESH_INTERVAL;
                countdown.innerHTML = Math.max(left4refresh, 0) + "";
            },
            error: function(err, _, _) {
                modalResult(error_message = "Couldn't load the service<br>list (" + err.status + ' error)<br><br><a class="btn btn-primary" href="javascript:window.location.reload(true);">Reload</a>');
                left4refresh = REFRESH_INTERVAL;
                countdown.innerHTML = Math.max(left4refresh, 0) + "";
            }
        });
    } else
        left4refresh--;
    countdown.innerHTML = Math.max(left4refresh, 0) + "";
    if (!manual)
        setTimeout(loadData, 1000);
}
loadData();

/* AJAX DATA UPDATING */
const smodal = document.getElementById('smodal'),
        pmodal = document.getElementById('pmodal'),
        sload = document.getElementById('sload'),
        sform = document.getElementById('sform'),
        ssave = document.getElementById('ssave');
let editingService = null;
function fillServiceSettings(id = null, name = null, type = null, logs = null, path = null,
                                attempts = null, duration = null, threshold = null) {
    editingService = id;
    let isnew = id == null;
    document.getElementById('sname').value = isnew ? '' : name;
    document.getElementById('stype').value = isnew ? '' : type;
    document.getElementById('slogs').value = isnew ? '' : logs;
    document.getElementById('spath').value = isnew ? '' : path;
    document.getElementById('sattempts').value = isnew ? '' : attempts;
    document.getElementById('sduration').value = isnew ? '' : duration;
    document.getElementById('sthresh').value = isnew ? '' : threshold;
    showHideWebPath();
    updateHint();
    ssave.disabled = false;
    sload.classList.replace('d-block', 'd-none');
    sform.classList.replace('d-none', 'd-block');
}
function loadServiceSettings(id) {
    sload.classList.replace('d-none', 'd-block');
    sform.classList.replace('d-block', 'd-none');
    ssave.disabled = true;
    $.ajax({
        dataType: "json",
        url: "./API/services/" + id,
        success: function(data) {
            fillServiceSettings(data['id'], data['name'], data['service'], data['log_path'],
                                data['web_path'], data['max_attempts'], data['block_duration'],
                                data['time_threshold']);
        },
        error: function(err, _, _) {
            bootstrap.Modal.getOrCreateInstance(smodal).hide();
            modalResult(error_message = "Couldn't load service settings (" + err.status + " error)");
        }
    });
}
function showHideWebPath() {
    document.getElementById('web-path').className = document.getElementById('stype').value === 'ssh' ? 'mb-3 d-none' : 'mb-3';
    document.getElementById('spath').required = document.getElementById('stype').value !== 'ssh';
}
function updateHint() {
    document.getElementById('hthresh').innerHTML = document.getElementById('sthresh').value ?? '_';
    document.getElementById('hattempts').innerHTML = document.getElementById('sattempts').value ?? '_';
    let duration = document.getElementById('sduration').value;
    document.getElementById('hduration').innerHTML = duration ? 'for ' + duration + ' minutes' : 'permanently';
}
function saveServiceSettings(e, form) {
    e.preventDefault();
    sload.classList.replace('d-none', 'd-block');
    sform.classList.replace('d-block', 'd-none');
    ssave.disabled = true;
    $.ajax({
        type: "POST",
        data: $(form).serialize(),
        url: "./API/services/" + (editingService ?? ''),
        success: function(data) {
            bootstrap.Modal.getOrCreateInstance(smodal).hide();
            modalResult();
            loadData(true);
        },
        error: function(err, _, _) {
            bootstrap.Modal.getOrCreateInstance(smodal).hide();
            modalResult(error_message = "Couldn't save service settings (" + err.status + " error)");
            loadData(true);
        }
    });
    editingService = null;
}
let deletionCandidate = null;
function setForDeletion(id) {
    deletionCandidate = id;
}
function confirmDeletion() {
    if (deletionCandidate == null)
        return;
    $.ajax({
        dataType: "json",
        url: "./API/services/" + deletionCandidate,
        type: 'DELETE',
        success: function(data) {
            modalResult(error_message = null, success_message = "Deleted successfully!");
        },
        error: function(err, _, _) {
            modalResult(error_message = "Couldn't delete (" + err.status + " error)");
            loadData(true);
        }
    })
}
function changePassword(e) {
    e.preventDefault();
    // TODO: send AJAX POST request
    let ajax_error = "The auth system is not<br>implemented yet"; // Blank means no error
    document.getElementById('pold').value = "";
    document.getElementById('pnew').value = "";
    document.getElementById('prepeat').value = "";
    bootstrap.Modal.getOrCreateInstance(pmodal).hide();
    modalResult(ajax_error);
}
function playPause(id) {
    $.ajax({
        type: "POST",
        url: "./API/services/" + id + '/playpause',
        success: function(data) {
            loadData(true);
        },
        error: function(err, _, _) {
            modalResult(error_message = "Couldn't toggle service's<br>state (" + err.status + " error)");
            loadData(true);
        }
    });
}
