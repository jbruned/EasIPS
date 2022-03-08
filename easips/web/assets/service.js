let id_path = window.location.href.split('/').pop();
const SERVICE_ID = !isNaN(id_path) ? id_path : new URL(window.location.href).searchParams.get("id") || '';

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
const ipPool = document.getElementById('ip-pool'),
        ipTable = document.getElementById('ip-table'),
        noResults = document.getElementById('no-results'),
        REFRESH_INTERVAL = 5; // In seconds
let ipCount = 0,
    left4refresh = 0;
function blockUnblock(addr, block=false) {
    $.ajax({
        type: "POST",
        url: "../API/services/" + SERVICE_ID + '/blocked',
        data: {"block": block, "ip_address": addr},
        success: function(data) {
            loadData(true);
            modalResult(error_message=null, success_message="IP address " + (block ? '' : 'un') + "blocked<br>successfully");
        },
        error: function(err, _, _) {
            modalResult(error_message = "Couldn't " + (block ? '' : 'un') + "block IP<br>(" + err.status + " error)");
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
        '                        <td' + (active ? '' : ' style="cursor: not-allowed;"') + '><a class="btn btn-' + (active ? 'primary' : 'secondary disabled') + '" href="javascript:blockUnblock(\'' + address + '\')"><i class="bi bi-unlock me-2"></i>Unblock</a></td>\n' + // trash3
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
                modalResult(error_message = "Couldn't load the list of<br>blocked IPs (" + err.status + ' error)<br><br><a class="btn btn-primary" href="javascript:window.location.reload(true);">Reload</a>');
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
const imodal = document.getElementById('imodal'),
        pmodal = document.getElementById('pmodal');
function addIp(e) {
    e.preventDefault();
    bootstrap.Modal.getOrCreateInstance(imodal).hide();
    blockUnblock(document.getElementById('ip').value, true);
    document.getElementById('ip').value = "";
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
