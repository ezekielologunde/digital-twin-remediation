# Excluded preliminary attempt and retained action definition

The preliminary batch b7f6534f0418437094f9a0e4052935a6 used Compose start for the target service. In two MongoDB-down short-range trials, its command receipt explicitly reported starting MongoDB before starting the target. Recovery therefore did not measure the intended target-only intervention.

That batch was stopped after four completed arms, with one additional arm interrupted. Its ledgers, source/configuration snapshots, container snapshot, deviation record and externally verified cleanup are retained. The entire preliminary batch is excluded from the corrected comparison, including its otherwise unaffected controls. It is not silently replaced or pooled with the retained data.

The retained batch starts the target using docker start with its verified container ID. It records MongoDB and Redis states after the action, and the analyzer verifies that the injected datastore state persisted. Probe decision rules are unchanged. This correction was made after observing the deviation; the retained experiment is development work, not a blind or confirmatory holdout.

An audit of thirty start-command receipts from earlier completed stages found no reported extra container starts. The new datastore-stop conditions exposed the previously latent command-scope issue. The broader lesson is to specify and verify the action's effects, not infer them from its service name.
