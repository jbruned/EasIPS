[].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]')).map(function (tooltipTriggerEl) {
  return new bootstrap.Tooltip(tooltipTriggerEl)
})

/* SUCCESS OR ERROR MESSAGE */
const success_modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('success-modal')),
        success_icon = document.getElementById('success-icon'),
        success_title = document.getElementById('success-title');
function modalResult(error_message = null, success_message = null) {
    success_modal.show();
    success_title.innerHTML = error_message || success_message || 'Saved successfully!';
    success_title.className = success_title.innerText.length > 55 ? 'h5' : 'h3';
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
        '            <div class="col-md-6 col-xl-4">\n' +
        '                <div class="card my-3">\n' +
        '                    <div class="card-header d-flex justify-content-between align-items-center"><div>\n' +
        '                        <h3 class="card-title m-0">' + name + '</h3>\n' +
        '                        <span class="text-' + (is_running ? 'success' : 'danger') + '" style="margin-left: -4px"><i class="bi bi-' + (is_running ? 'play' : 'pause') + '-fill me-1"></i>' + (is_running ? 'Running' : 'Paused') + '</h3>\n' +
        '                    </div><div class="btn-group-vertical" role="group" aria-label="Service options"><a class="btn btn-warning btn-zoom" href="javascript:playPause(' + id + ')"><i class="bi bi-' + (is_running ? 'pause' : 'play') + '-fill" style="margin: 0px -5px"></i></a><a class="btn btn-danger btn-zoom" data-bs-toggle="modal" data-bs-target="#confirm-delete" onclick="setForDeletion(' + id + ')"><i class="bi bi-trash3-fill" style="margin: 0px -5px"></i></a></div></div>\n' +
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
            error: function(err, _, __) {
                let error = "Couldn't load the service<br>list (" + err.status + ' error)';
                if (err.status == 0)
                    error = "Couldn't connect to the server, is it running?";
                modalResult(error + '<br><br><a class="btn btn-primary" href="javascript:window.location.reload(true);">Reload</a>');
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
    let isnew = id == null, is_easips = type === 'easips';
    document.getElementById('sname').value = isnew ? '' : name;
    document.getElementById('stype').required = !is_easips;
    if (is_easips) {
        document.getElementById('stype').classList.add('d-none');
        document.getElementById('lock-row').classList.add('d-none');
        document.getElementById('stype-easips').classList.remove('d-none');
    } else {
        document.getElementById('stype').classList.remove('d-none');
        document.getElementById('lock-row').classList.remove('d-none');
        document.getElementById('stype-easips').classList.add('d-none');
    }
    document.getElementById('stype').value = isnew ? '' : type;
    selectService();
    document.getElementById('spath').required = !is_easips;
    document.getElementById('slock').required = !is_easips;
    document.getElementById('slogs').value = isnew ? '' : logs;
    document.getElementById('spath').value = isnew ? '' : path;
    document.getElementById('slock').value = isnew ? '' : isNaN(path) ? (path.includes('/') ? 'htaccess' : 'hosts') : 'firewall';
    selectLock();
    document.getElementById('sattempts').value = isnew ? '' : attempts;
    document.getElementById('sduration').value = isnew ? '' : duration;
    document.getElementById('sthresh').value = isnew ? '' : threshold;
    updateHint();
    ssave.disabled = false;
    document.getElementById('err-path').classList.add('d-none')
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
            fillServiceSettings(data['id'], data['name'], data['service'], data['log_path'], data['lock_resource'],
                                data['max_attempts'], data['block_duration'], data['time_threshold']);
        },
        error: function(err, _, __) {
            bootstrap.Modal.getOrCreateInstance(smodal).hide();
            modalResult("Couldn't load service settings (" + err.status + " error)");
        }
    });
}
const VALUES_SERVICES = {
    '': 'Service',
    'easips': 'EasIPS',
    'joomla': 'Joomla',
    'wordpress': 'WordPress',
    'ssh': 'SSH',
    'phpmyadmin': 'phpMyAdmin'
}
function selectService() {
    let service = document.getElementById('stype').value, value = VALUES_SERVICES[service] ?? 'Service';
    if (document.getElementById('stype').classList.contains('d-none'))
        value = VALUES_SERVICES['easips'];
    if (service === 'phpmyadmin' || service === 'wordpress')
        document.getElementById('service-name').innerText = "Apache";
    else
        document.getElementById('service-name').innerText = value;
    document.getElementById('service-name-2').innerText = value === 'Service' ? "First choose a service from the list" : "Default values for " + value + " will be used";
    document.getElementById('service-name-3').innerText = value;
    document.getElementById('external-service-settings').innerText = value + " installation settings";
    document.getElementById('option-htaccess').disabled = service === 'ssh';
}
function selectLock(from_select = false) {
    if (document.getElementById('stype').classList.contains('d-none'))
        return;
    if (from_select)
        document.getElementById('spath').value = '';
    let value = document.getElementById('slock').value;
    if (value === 'htaccess' || value === 'hosts') {
        document.getElementById('lock-arg-name').innerText = value === 'htaccess' ? "Web folder path" : "Daemon name";
        document.getElementById('spath').type = "text";
        document.getElementById('spath').removeAttribute("min");
        document.getElementById('spath').removeAttribute("max");
        document.getElementById('spath').removeAttribute("step");
    } else {
        document.getElementById('lock-arg-name').innerText = "Port number";
        document.getElementById('spath').type = "number";
        document.getElementById('spath').min = 0;
        document.getElementById('spath').max = 65535;
        document.getElementById('spath').step = 1;
    }
    // document.getElementById('service-name-3').innerText = VALUES_SERVICES[value];
}
function bestSettings() {
    if (document.getElementById('stype').classList.contains('d-none'))
        document.getElementById('slogs').value = 'easips.log';
    let service = document.getElementById('stype').value;
    if (service === 'ssh') {
        document.getElementById('slogs').value = '/var/log/auth.log';
        document.getElementById('slock').value = 'hosts';
        selectLock();
        document.getElementById('spath').value = 'sshd';
    } else if (service === 'joomla') {
        document.getElementById('slogs').value = '/var/www/html/administrator/logs/error.php';
        document.getElementById('slock').value = 'htaccess';
        selectLock();
        document.getElementById('spath').value = '/var/www/html/administrator';
    } else if (service === 'wordpress') {
        document.getElementById('slogs').value = '/var/log/apache2/access.log';
        document.getElementById('slock').value = 'htaccess';
        selectLock();
        document.getElementById('spath').value = '/var/www/html/wp-admin';
    } else if (service === 'phpmyadmin') {
        document.getElementById('slogs').value = '/var/log/apache2/access.log';
        document.getElementById('slock').value = 'htaccess';
        selectLock();
        document.getElementById('spath').value = '/placeholder/usr/share/phpmyadmin';
    }
}
function updateHint() {
    let value = document.getElementById('sthresh').value ?? 0;
    document.getElementById('hthresh').innerHTML = value == 0 ? '_' : value;
    value = document.getElementById('sattempts').value;
    document.getElementById('hattempts').innerHTML = value == 0 ? '_' : value;
    value = document.getElementById('sduration').value;
    document.getElementById('hduration').innerHTML = value == 0 ? 'permanently' : 'for ' + value + ' minutes';
}
function saveServiceSettings(e, form) {
    e.preventDefault();
    if (!document.getElementById('stype').classList.contains('d-none')) {
        if (document.getElementById('slock').value === 'htaccess'
            && !(document.getElementById('spath').value ?? '').includes('/')) {
            document.getElementById('err-path').innerText = "Path must contain '/'";
            document.getElementById('err-path').classList.remove('d-none')
            return;
        } else if(document.getElementById('slock').value === 'hosts'
                  && !isNaN(document.getElementById('spath').value)) {
            document.getElementById('err-path').innerText = "Name can't be a number";
            document.getElementById('err-path').classList.remove('d-none')
            return;
        } else if(document.getElementById('slock').value === 'hosts'
                  && document.getElementById('spath').value.includes(' ')) {
            document.getElementById('err-path').innerText = "Name can't have spaces";
            document.getElementById('err-path').classList.remove('d-none')
            return;
        } else
            document.getElementById('err-path').classList.add('d-none')
    }
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
        error: function(err, _, __) {
            bootstrap.Modal.getOrCreateInstance(smodal).hide();
            let error = "Couldn't save service settings (" + err.status + " error)";
            if (err.status === 418)
                error = "The service was stopped due to invalid configuration. A possible cause could be that the specified paths/files don't exist or you don't have write permission.";
            modalResult(error);
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
            modalResult(null, "Deleted successfully!");
            loadData(true);
        },
        error: function(err, _, __) {
            let error_message = "Couldn't delete (" + err.status + " error)";
            if (err.status === 401)
                error_message = "EasIPS service can't be deleted! You can stop it but we discourage doing so";
            modalResult(error_message);
            loadData(true);
        }
    })
}
function changePassword(event, form) {
    event.preventDefault();
    $.ajax({
        type: "POST",
        data: $(form).serialize(),
        url: "./API/password",
        success: function(data) {
            document.getElementById('pold').value = "";
            document.getElementById('pnew').value = "";
            document.getElementById('prepeat').value = "";
            bootstrap.Modal.getOrCreateInstance(pmodal).hide();
            modalResult(null, 'Password updated successfully!');
        },
        error: function(err, _, __) {
            document.getElementById('pold').value = "";
            document.getElementById('pnew').value = "";
            document.getElementById('prepeat').value = "";
            bootstrap.Modal.getOrCreateInstance(pmodal).hide();
            let error = "Couldn't change password (" + err.status + " error)";
            if (err.status === 400)
                error = "New password should have at least 5 characters, and both fields must match";
            else if (err.status === 401)
                error = "The old password is not correct";
            else if (err.status === 403) {
                document.location.reload();
                error = "EasIPS is obviously also protected against too many login attempts. Oops!"
            }
            modalResult(error);
        }
    });
}
function playPause(id) {
    $.ajax({
        type: "POST",
        url: "./API/services/" + id + '/playpause',
        success: function(data) {
            loadData(true);
        },
        error: function(err, _, __) {
            let error = "Couldn't toggle service's state (" + err.status + " error)";
            if (err.status === 418)
                error = "Couldn't start service, a possible cause could be that the specified paths/files don't exist or you don't have write permission.";
            modalResult(error);
            loadData(true);
        }
    });
}
