let id_path = window.location.href.split('/').pop();
const SERVICE_ID = !isNaN(id_path) ? id_path : new URL(window.location.href).searchParams.get("id") || '';

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
const ipPool = document.getElementById('ip-pool'),
      ipTable = document.getElementById('ip-table'),
      noResults = document.getElementById('no-results'),
      staticPool = document.getElementById('static-pool'),
      staticTable = document.getElementById('static-table'),
      noStatic = document.getElementById('no-static'),
      REFRESH_INTERVAL = 5; // In seconds
let ipCount = 0,
    left4refresh = 0;
function blockUnblock(addr, block=false, static_rule=false) {
    $.ajax({
        type: "POST",
        url: "../API/services/" + SERVICE_ID + '/' + (static_rule ? 'static' : 'blocked'),
        data: {"block": block, "ip_address": addr},
        success: function(data) {
            loadData(true);
            modalResult(null, "IP address " + (block ? '' : 'un') + "blocked<br>successfully");
        },
        error: function(err, _, __) {
            let error = "Couldn't " + (block ? '' : 'un') + "block IP<br>(" + err.status + " error)";
            if (err.status === 418)
                error = "Couldn't " + (block ? '' : 'un') + "block IP because the service is stopped";
            if (err.status === 400)
                error = "Invalid IP address";
            modalResult(error);
            loadData(true);
        }
    });
}
function removeStatic(addr) {
    $.ajax({
        type: "DELETE",
        url: "../API/services/" + SERVICE_ID + '/static',
        data: {"ip_address": addr},
        success: function(data) {
            loadStaticRules();
            loadData(true);
            // modalResult(null, "Static rule removed<br>successfully");
        },
        error: function(err, _, __) {
            let error = "Couldn't remove static rule<br>(" + err.status + " error)";
            if (err.status === 418)
                error = "Couldn't remove static rule because the service is stopped";
            if (err.status === 400)
                error = "Invalid IP address";
            modalResult(error);
            loadStaticRules();
            loadData(true);
        }
    });
}
function loadIp (address, block_time, active) {
    ipPool.innerHTML +=
        "                    <tr>\n" +
        "                        <td>" + (++ipCount) + "</td>\n" +
        "                        <td>" + address + "</td>\n" +
        "                        <td>" + block_time + "</td>\n" +
        "                        <td>" + (active ? 'Active' : 'Unblocked') + "</td>\n" +
        '                        <td' + (active ? '' : ' style="cursor: not-allowed;"') + '>' +
        '                            <a class="btn btn-' + (active ? 'primary' : 'secondary disabled') + '" href="javascript:' + (block_time === 'Blacklisted' ? ("removeStatic('" + address + "')") : ("blockUnblock('" + address + "', false, false)")) + '"><i class="bi bi-unlock me-2"></i>Unblock</a>' +
        '                            <a class="btn btn-primary" href="javascript:blockUnblock(\'' + address + '\', false, true)"><i class="bi bi-check2-circle me-2"></i>Whitelist</a>' +
        '                            <a class="btn btn-' + (block_time === 'Blacklisted' ? 'secondary disabled' : 'primary') + '" href="javascript:blockUnblock(\'' + address + '\', true, true)"><i class="bi bi-shield-x me-2"></i>Blacklist</a>' +
        '                        </td>\n' + // trash3
        "                    </tr>"
}
function loadData (manual=false) {
    if (manual || left4refresh == 0) {
        $.ajax({
            dataType: "json",
            url: "../API/services/" + SERVICE_ID + "/blocked",
            type: 'GET',
            success: function(data) {
                ipCount = 0;
                ipPool.innerHTML = '';
                for (let i = 0; i < data.length; i++)
                    loadIp(data[i]['ip_address'], data[i]['blocked_at'], data[i]['active']);
                noResults.className = 'text-center my-5 text-muted d-' + (data.length == 0 ? 'block' : 'none');
                left4refresh = REFRESH_INTERVAL;
                countdown.innerHTML = Math.max(left4refresh, 0) + "";
            },
            error: function(err, _, _) {
                let error = "Couldn't load the blocked<br>IPs list (" + err.status + ' error)';
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

function loadStaticRule(address, block_time, blocked) {
    staticPool.innerHTML +=
        "                    <tr>\n" +
        "                        <td>" + address + "</td>\n" +
        "                        <td>" + block_time + "</td>\n" +
        "                        <td>" + (blocked ? 'Blacklisted' : 'Whitelisted') + "</td>\n" +
        '                        <td>\n' +
        '                            <a class="btn btn-danger rounded-circle p-2" href="javascript:removeStatic(\'' + address + '\')"><i class="bi bi-trash3"></i></a>\n' +
        '                        </td>\n' + // trash3
        "                    </tr>"
}
function loadStaticRules() {
    $.ajax({
        dataType: "json",
        url: "../API/services/" + SERVICE_ID + "/static",
        type: 'GET',
        success: function(data) {
            staticPool.innerHTML = '';
            for (let i = 0; i < data.length; i++)
                loadStaticRule(data[i]['ip_address'], data[i]['added_at'], data[i]['blocked']);
            noStatic.className = 'text-center my-5 text-muted d-' + (data.length == 0 ? 'block' : 'none');
        },
        error: function(err, _, __) {
            let error = "Couldn't load the static<br>rule list (" + err.status + ' error)';
            if (err.status == 0)
                error = "Couldn't connect to the server, is it running?";
            modalResult(error + '<br><br><a class="btn btn-primary" href="javascript:window.location.reload(true);">Reload</a>');
            left4refresh = REFRESH_INTERVAL;
            countdown.innerHTML = Math.max(left4refresh, 0) + "";
        }
    });
}
loadData();

/* AJAX DATA UPDATING */
const imodal = document.getElementById('imodal'),
      pmodal = document.getElementById('pmodal');
function addIp() {
    bootstrap.Modal.getOrCreateInstance(imodal).hide();
    blockUnblock(document.getElementById('ip').value, !document.getElementById('rule-white').checked,
        !document.getElementById('rule-dynamic').checked);
    document.getElementById('ip').value = "";
}
function changePassword(event, form) {
    event.preventDefault();
    $.ajax({
        type: "POST",
        data: $(form).serialize(),
        url: "../API/password",
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
