|---------------------------------------------------------------------------------------------------|
| Function	                     |            Description                                           |
| --------------------------------------------------------------------------------------------------|
| execute(script) (via file)	   |     Run Lua script from a file                                   |
| get_expire_date()              |    	Check subscription expiration date                          |
| redeem(key)	                   |     Activate a license                                           |
| reset_hwid()	                 |     Hardware changed — reset HWID                                |   
| get_roblox_processes()	       |     Get all running Roblox processes                             |
| get_synz_roblox_instances()	   |       Get only injected Synapse Z instances                      |
| is_synz(pid)	                 |     Check if a specific process is a Synapse Z instance          | 
|              SynapseZAPI2 (Python callback output)	                                              |
| start_instances_timer()	       |     Start auto-detection of Roblox sessions                      |
| on_session_output(cb)	         |      Receive print()/warn()/error() output from Lua scripts      |
| on_session_added(cb)	         |      Callback when a new injected instance is detected           | 
| execute(script) (via pipe)	   |      Execute script via named pipe, returning output             |
|---------------------------------------------------------------------------------------------------|
