# TODO: implement API using Flask with two GET endpoints:
# - /services/ -> Return a list of services in JSON (fields: service id, name,
#                 blocked IPs, both currently and past 24h, minutes since last block)
# - /services/{id} -> Return a list of blocked IPs in JSON (fields: address,
#                     minutes since block started)

# Flask should also deliver static HTML files (login, dashboard and service)

# Flask should also have POST endpoints to receive AJAX requests (unblock IPs, create services...)
