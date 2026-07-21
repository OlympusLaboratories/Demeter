
	ThreadsHuddlesRecapDrafts & sentDirectorieslarge_blue_squareEngai-toolsengeng-announceeng-buildeng-snippetsprodsecurityswe-teamlarge_green_squareOfficegame-nightgeneralhealthlunchofficeoffice-sfpets-maticrandomvacationswfhlarge_yellow_squareML Inframl-infraplatform-infraplatform-infra-gitplatform-infra-linearplatform-infra-teamproject-flyteproject-model-evaluationlarge_orange_squareML RnDmarket-simulationml-cycleml-reading-groupml-researchml-teampower-modelsprice-modelsweather-modelslarge_red_squareAlertsalerts-ftlalerts-infraalerts-platform-infraalerts-prod-modelsalerts-retailalerts-tradingbot-message-testfeed-buildkite-pipeline-orchestratork8s-pods-alerts-alllarge_purple_squareStoragestoragestorage-engstorage-flytestorage-operations-internallarge_blue_circleRetailretailretail-engretail-won-dealslarge_green_circleEnergycaisocarboncrrsenergy-reading-groupercoteuropeiceisonemisonyisopjmspplarge_yellow_circleHiringrecruiting-publicExternal connectionsbuildkite-supportgridmatic-zencorewandb-gridmaticChannelsdbteng-build-statusgridmatic-dev-early-adoptersstorage-operationsDirect messagesMarkTravis ThompsonJamie RayaimunVrinda VasavadaKristen Chatley, Vrinda VasavadaVictorSophie Krivokapic-ZhouDylan LarrabeeyouAgents & appsThreadsMark Mark and youDylan Larrabee  [11:08 AM]
Some setup to be able to test snapshotting locally in kubernetes-in-docker
https://gitlab.com/gridmatic/foundation/gridmatic-dev/-/merge_requests/488
Mark  [12:48 PM]
Sweet. I'll look after lunch 

Reply…Also send as direct messageplatform-infra-team Mark, Victor, and Travis ThompsonMark  [10:32 AM]
We need to come up with a strategy for dealing with OOMs on rdev workstations, which will require getting into a lot of details with kube/GKE and OOM kill mechanisms, as well as how we surface this to users.  Who would be interested in working on this?
Victor  [10:34 AM]
im down
Mark  [10:34 AM]
ok, let's discuss today
Victor  [10:34 AM]
:books:
Mark  [10:37 AM]
There is a ticket here https://linear.app/gridmatic/issue/PLAT-2059/rdev-contain-workstation-ooms-memory-limits-single-process-oom-kill.  Claude tried to come up with an MR, but i think this deserves more thought, and for us to understand more in-depth as a team
LinearOpenTravis Thompson  [10:54 AM]
rdevd spawns all the processes, it should be able to supervise and kill before kube does 

Reply…Also send to platform-infra-teamplatform-infra-team Mark and youDylan Larrabee  [12:34 PM]
https://gridmatic.slack.com/archives/C0B9ZL61ZDE/p1784144057437049
I shipped the new rdev feature that lets users select the storage size of their instance or expand the storage size of an existing instance
still testing it out but it appears to be working well - please let me know if there are any issues found with it!Posted in gridmatic-dev-early-adopters | Jul 15th | View messageMark  [12:49 PM]
Awesome!

Reply…Also send to platform-infra-teameng Milo Webster and youMilo Webster  [10:47 AM]
Is tlaloc-env/kube/apps/predict-models/uma/kustomization.yaml for alerting? We should remove predict model entries from this after suspending or deleting the corresponding cron right?
Dylan Larrabee  [11:44 AM]
yes, also there is a linting job that runs in the MR pipeline that should remind you (fail the pipeline) to remove references from kustomization.yaml that were deleted
Milo Webster  [12:22 PM]
Cool, thanks!

Reply…Also send to engplatform-infra-team Travis Thompson, aimun, and 2 othersSaved for laterTravis Thompson  [5:22 PM]
I forgot to mention, we need ideas for a team event, and dates; let's target August? brainstorm ideas everyone! also I was thinking of using some of our budget to order team t-shirts and/or hats; ideas for that would be good too
aimun  [7:20 PM]
I thought the entire budget was being blown on fancy food
aimun  [7:21 PM]
What about  :mark: shirts
aimun  [7:22 PM]
I think an escape room would be fun if everyone enjoys that type of activity
Nell  [10:30 AM]
I like escape rooms and fancy food if they have vegetarian options
Nell  [10:31 AM]
Could also do some kind of workshop? Like an art class or a cooking class or a something cooler class
Dylan Larrabee  [10:32 AM]
I'm also a big fan of escape rooms. Maybe an escape room and dinner? (Fancy-ness dependent on remaining budget I suppose)
aimun  [10:34 AM]
@Travis Thompson If we do Quince will there be anything left over
aimun  [10:34 AM]
Or is that an all-in type of thing
Travis Thompson  [10:34 AM]
I think we'd have some left over if we did their lunch
Travis Thompson  [10:34 AM]
which I think is all we can afford anyway lol
Travis Thompson  [10:35 AM]
I'm not sure about veg options though, I was planning to just not be vegitarian for Quince, so might need to do some place else
aimun  [10:37 AM]
I believe they have a veg menu but you have to call ahead
Travis Thompson  [10:47 AM]
good to know
Travis Thompson  [10:47 AM]
I think there is an escape room in fidi
Travis Thompson  [10:47 AM]
looks like there are 3
aimun  [10:48 AM]
If it works logistically, imo the best escape room in the city by far is Palace Games
Travis Thompson  [10:48 AM]
yeah I mean, not that hard to get over there
Dylan Larrabee  [10:50 AM]
I've done the Roosevelt and Attraction rooms at Palace Games, that place is great (edited) 
Travis Thompson  [10:52 AM]
quince lunch is $220/person and is 5 courses, if that's what we want to do; and they have a noon seating on a Friday
Travis Thompson  [10:52 AM]
otherwise I'm sure we could do something more casual and still have a fun time, I'm down for whatever
Travis Thompson  [10:53 AM]
there's a bunch of good places on Chestnut st over by the palace
Travis Thompson  [10:56 AM]
oh there's also Wildseed on Union, that place is excellent and 100% vegan

Reply…Also send to platform-infra-teameng-build Doug, Melody, and 3 othersDoug  [10:48 AM]
FYI seems like master builds are failing due to retail build, pyright typecheck failing
Doug  [10:49 AM]
@Remi @Melody fyi seems like this may have been introduced here https://gitlab.com/gridmatic/tlaloc/-/commit/e3ccc020323ede58d0d393d853a0fecc9757accc
Melody  [11:16 AM]
Yikes, thanks for the heads-up! Putting up a fix
Melody  [11:41 AM]
Merged (https://gitlab.com/gridmatic/tlaloc/-/merge_requests/14164), thanks again for the heads-up!

Cause: Unlucky timing between feature branch and db column deprecation. Remi created a feature branch that passed tests -> I merged a migration that deprecated a column -> Remi merged in the feature branch into master which referenced the deprecated column.

@Dylan Larrabee I thought that buildkite had a check for outdated commits in comparison to master? The last I remembered was 100 commits - maybe the number of commits between the 2 MRs was just under 100?
Dylan Larrabee  [12:26 PM]
I think the number was changed because people found it annoying- I'll need to check what the value is now
Kevin Qi  [2:07 PM]
good summary @Melody, thank you for resolving and thanks @Doug for raising
Travis Thompson  [4:36 PM]
it might be less annoying if we enforced squash commits
Travis Thompson  [4:36 PM]
then if we set it to like 5 it's five merged MRs
Kevin Qi  [10:32 AM]
this is a pretty rare situation since we almost never drop columns, which is one of the few things that creates hard backward incompatibility

I’m definitely a fan of cleaning things up so I’m all in favor of doing this occasionally. Perhaps we could have a “drop column” claude skill which checks for active MRs which might have stale references or something
Kevin Qi  [10:32 AM]
maybe can pair with you on that @Melody e.g. for task week

Reply…Also send to eng-buildplatform-infra Madeline Liao, Vrinda Vasavada, and 2 othersMadeline Liao  [10:33 AM]
I merged an update to 3 cronjobs yesterday (MR) - two of them ran successfully today but one failed and tried to run the old command instead

These new jobs ran successfully:
ercot_retail_uma_predict_v13  (job) 
ercot_retail_loads_v13 (job)

But the existing job (that I modified in the MR) failed to update:
ercot_retail/staging (job)
I had updated the cronjob from vesper_retail_v3 -> v5, but the YAML for the job shows that the command is still running vesper_retail_v3




Feels like I’m missing something silly :think-hard:  can I get help with this? (Lmk if not the right channel)
Vrinda Vasavada  [10:49 AM]
seems like possibly an issue with ArgoCD not updating the staging jobs, looking more into why this is happening
Vrinda Vasavada  [10:52 AM]
per claude, @Mark could I get access to the ArgoCD UI to verify / fix?

TLDR for your coworker: her MR is correct and merged; the cronjob didn't update because the ArgoCD app bid-ercot-retail has been stuck in a failed sync-retry loop since at least July 6 (before her merge), endlessly re-applying an old
  revision. The new v13 jobs deployed because they live in a different ArgoCD app that isn't stuck.

  Evidence:

  1. origin/main has v5 in kube/apps/bid-models/ercot_retail/staging/cronjob.yaml (commit 7ecbb153549, merged Jul 9 17:07 UTC).
  2. The cluster CronJob bid-models-ercot-retail-staging (ns production, tlaloc us-central1-c cluster) still has the v3 command, so today's 10:00 CT run spawned a v3 job, which failed.
  3. Audit logs show argocd-manager patching both ercot_retail cronjobs every 5 minutes for days, and the patch only touches resources.limits — never the args. ArgoCD's desired state is rendered from a pre-merge revision because the stuck sync
  operation is pinned to the revision it started with, and retry.limit = -1 in the ApplicationSet module retries it forever. The diff never converges because GKE Autopilot's admission webhook keeps mutating the pod resources back. No other
  bid-model cronjobs are in this loop.

  Fix:

  1. In the ArgoCD UI, open bid-ercot-retail, terminate the in-flight sync operation, then sync. Verify with kubectl -n production get cronjob bid-models-ercot-retail-staging -o yaml | grep vesper — should show v5.
  2. Durable fix: declare requests equal to limits in both ercot_retail cronjob manifests so Autopilot's mutation is a no-op, and flag the infinite retry.limit = -1 in terraform/modules/argocd-applicationset/main.tf to ml-infra — a
  never-converging diff currently pins an app to a stale revision silently (the # touch: force ArgoCD re-sync comment on cflats1 suggests they've hit this before).Travis Thompson  [10:53 AM]
@Vrinda Vasavada mark can get you UI access but the argo cli tool also works great and doesn't require UI access, you can point it directly at argo via kubectl port forward
Travis Thompson  [10:53 AM]
claude can use it too
Vrinda Vasavada  [10:53 AM]
okay great let me try that out thanks!
Vrinda Vasavada  [11:16 AM]
https://gitlab.com/gridmatic/tlaloc-env/-/merge_requests/2525
Vrinda Vasavada  [11:25 AM]
one question for you @Travis Thompson -- https://gitlab.com/gridmatic/tlaloc-env/-/blob/main/terraform/modules/argocd-applicationset/main.tf?ref_type=heads#L108 currently, this hardcodes an infinite number of retries, which means that we don't get the sync failed alerts on this type of issue and it just retries every 5 minutes silently! is it okay if I change this to something like 5 so failures terminate and alert?
Travis Thompson  [11:37 AM]
yeah we should probably change that, @Dylan Larrabee do you remember why this got set this way?
Vrinda Vasavada  [11:44 AM]
@Madeline Liao should be all set now, I see vesper_retail_v5 in staging here now! (edited) 
Madeline Liao  [11:45 AM]
yay thank you!
Dylan Larrabee  [11:47 AM]
I think that was intentional, so that you can make a MR with the kube manifest changes and the terraform changes at once;
you can apply the terraform changes and it will keep retrying until you merge the mainfest changes in and it will just get picked up

otherwise one would need two MRs - merge in the manifest changes with one then another to apply the terraform changes to pull in the manifest and deploy it
Travis Thompson  [11:48 AM]
that makes sense, I guess I've gone the two MR route and pointed argo at my branch initially; maybe we should rethink the way we do argo and move the templates to helm charts in tlaloc (edited) 
Travis Thompson  [11:49 AM]
I'd like to do that eventually
Travis Thompson  [11:49 AM]
but not a short term fix :slightly_smiling_face:
Vrinda Vasavada  [11:55 AM]
sorry I might be missing something but I thought that in the case that your MR has both kube manifest changes and terraform changes the flow would be like:

atlantis would apply the terraform changes while the MR is open. argoCD creates the app but since the app is not on main yet, no syncing or retrying is done
then on merge, argoCD re-checks git, sees the new commit, and kicks off a brand-new sync


in which case, a finite retry limit would still work and allow you to have manifest changes and terraform changes in one MR? (edited) 
Dylan Larrabee  [11:58 AM]
argoCD creates the app but since the app is not on main yet, no syncing or retrying is done
it cant find the kube mainfest on main yet so it is in an unhealthy state and keeps retrying indefinitely (so that when it is merged to main it is automatically picked up and becomes healthy) 
Vrinda Vasavada  [12:11 PM]
okay! i don't 100% follow the mechanics of it but will just add an alert instead to catch this kind of issue in the future!
Vrinda Vasavada  [12:40 PM]
https://gitlab.com/gridmatic/tlaloc-env/-/merge_requests/2526

Reply…Also send to platform-infraeng-build Buildkite Builds, Vrinda Vasavada, and 2 othersBuildkite Builds  [3:12 PM]
[Failed] Tlaloc (master) #24206Merge branch 'make_caiso_tune' into 'master' - @irene (82db027d06)
View BuildTlaloc master build failing! cc @platform-infra-oncall!Vrinda Vasavada  [3:13 PM]
I think this is the same as the original failure above https://gridmatic.slack.com/archives/C08M90F8A8M/p1783623093290969?thread_ts=1783623023.164649&cid=C08M90F8A8M fyi @irene!
this is a weird one @Lucas Orts I don't see how this is related to the timeout change though
2026-07-09 11:50:19 PDT
	FAILED python/tlaloc/capa/tests/simulations/miso/dam/simulate_test.py::test_simulate_miso_day_ahead_market_reduced - AssertionError:
2026-07-09 11:50:19 PDT
	Not equal to tolerance rtol=0.01, atol=0.5
From a thread in eng-build | Jul 9th | View replyPhilippe  [3:15 PM]
Fix for this was merged to master ~30 mins ago fyi
Philippe  [3:16 PM]
and then master failed...damn
Philippe  [3:16 PM]
but on the Retail job
Philippe  [3:16 PM]
so unrelated I think
Melody  [11:42 AM]
Just merged retail job fix:  https://gridmatic.slack.com/archives/C08M90F8A8M/p1783708907811659?thread_ts=1783705739.664299&cid=C08M90F8A8M
Merged (https://gitlab.com/gridmatic/tlaloc/-/merge_requests/14164), thanks again for the heads-up!

Cause: Unlucky timing between feature branch and db column deprecation. Remi created a feature branch that passed tests -> I merged a migration that deprecated a column -> Remi merged in the feature branch into master which referenced the deprecated column.

@Dylan Larrabee I thought that buildkite had a check for outdated commits in comparison to master? The last I remembered was 100 commits - maybe the number of commits between the 2 MRs was just under 100?
From a thread in eng-build | Jul 10th | View reply
Reply…Also send to eng-buildprod Matt Wytock, Austin Park, and 4 othersMatt Wytock  [9:24 AM]
CAISO model failing due to missing NAM data @models-caiso https://gridmatic.slack.com/archives/C03UH0LF97G/p1782922760565389
Triggered: Trading - bid model script failed on market:caisoBid script caiso/vesper_v2_py312 failed.

Link to logs of pod

Link to trading reliability Dashboard

@slack-alerts-trading

4 events triggered this monitor, here is the last one.

 Tagsmarket:caisoNotified@slack-alerts-tradingShow 21 more repliesLinear  [12:53 PM]
Dylan Larrabee created issue PLAT-1891LinearOpenLinear  [11:28 AM]
Dylan Larrabee changed status to Done for PLAT-1891 Parameterize compute specs per ruleAdded by Linear
Reply…Also send to prodplatform-infra-team Travis Thompson, Mark, and youSaved for laterTravis Thompson  [5:10 PM]
@Dylan Larrabee since you're on call, when you get a sec tomorrow can you onboard Ivy to gridops via firebase? https://linear.app/gridmatic/issue/PLAT-1978/give-ivy-access-to-gridops
LinearOpenTravis Thompson  [5:10 PM]
the request came in improperly
Dylan Larrabee  [5:17 PM]
Sure thing
Dylan Larrabee  [5:18 PM]
I don't think I've done this before, is there an onboarding doc anywhere to follow?
Travis Thompson  [5:19 PM]
I don't think so, it's just adding her in the firebase admin console
Travis Thompson  [5:19 PM]
we should probably have a notion page and consolidate all this info
Travis Thompson  [5:19 PM]
in platform infra notion
Travis Thompson  [5:23 PM]
https://app.notion.com/p/gridmatic/Access-Requests-3996763b19a68066a4fbda088e7a3e1f?source=copy_link
:lock: Access RequestsArgo CDCreated by Travis Thompson | Jul 9th | Added by NotionTravis Thompson  [5:23 PM]
created a page to start documenting it, we should expand that as we need to, and include the other old apps I'm forgetting about
Travis Thompson  [5:25 PM]
most of these are handled via Okta cc @Mark
Mark  [5:59 PM]
Yeah, we should okta-ize gridops at some point
Travis Thompson  [5:59 PM]
we need to have a real product roadmap around gridops / market ops as a serivce
Dylan Larrabee  [8:46 AM]
I'll need help to do this; it says I need to be an owner (edited) 
Screenshot 2026-07-10 at 8.45.57 AM.png 
Reply…Also send to platform-infra-teamalerts-platform-infra Grafana, Linear, and 3 othersGrafana  [2:04 PM]
@platform-infra-oncall[FIRING:1] DA COP submission missing (gridops ERCOT) Gridops (true critical platform)**Firing**

Value: A=-1, B=-1, C=-1
Labels:
 - alertname = DA COP submission missing (gridops ERCOT)
 - grafana_folder = Gridops
 Grafana v12.3.1 | Jul 9th | Added by GrafanaDylan Larrabee  [2:24 PM]
:claude:
:red_circle: DA COP submission missing — root-caused
The COP submission worker (gridops-cop-submission-temporal-worker-prod) has been crash-looping since ~9pm CT last night, right after an auto-deploy. It runs out of memory and dies within seconds of starting, so when today's submission was supposed to run at 2:08pm CT there was no healthy worker to do it — the job never ran (nothing errored). Both prod and dev workers hit this; no other services affected.
The workers are capped at 0.5G memory, and last night's build pushed startup over that limit.

Good news: today's run is still queued — the trigger fired on schedule and the workflow is sitting open in Temporal waiting for a worker. Once the worker is healthy again it should pick it up and submit automatically, no manual trigger needed (assuming it hasn't hit the workflow timeout or the DAM deadline by then — worth confirming in Temporal).

Fix (MR in tlaloc-env, off main): bump memory requests and limits from 0.5G → 2G in both files:
kube/apps/us-west1/gridops-cop-submission/cop-submission-temporal-worker-prod/deployment.yaml
kube/apps/us-west1/gridops-cop-submission/cop-submission-temporal-worker-dev/deployment.yaml


Done when both workers stay running and today's queued submission lands. Separately, someone should look into why the worker's memory use jumped in last night's tlaloc build.Linear  [2:24 PM]
Dylan Larrabee created issue PLAT-1974LinearOpenTravis Thompson  [2:25 PM]
oh wow, thanks dylan, good find
Travis Thompson  [2:25 PM]
wonder why the memory foot print changed, perhaps python 3.12 + proto upgrade
Travis Thompson  [2:26 PM]
we definitely need a claude on call bot, holy cow
Dylan Larrabee  [2:29 PM]
MR (edited) 
Victor  [2:29 PM]
weve had memory issues elsewhere too https://gridmatic.slack.com/archives/C07B0P4DFC5/p1783628707626629?thread_ts=1783621210.366129&cid=C07B0P4DFC5
Here is the potential issue and solution:

08:25— cronjob runs green
09:03— new prod image rolls out, includes8988114072"Add cuopt dependency" (commit)
9:25 and after: same jobs start hitting backoff limit 


From a thread in storage-operations-internal | Jul 9th | View replyTravis Thompson  [2:29 PM]
ahh it was @Amir's fault!
Travis Thompson  [2:30 PM]
@Dylan Larrabee can you open open a follow up ticket to add alerts for crashloopbackoff on any deployment we own?
Dylan Larrabee  [2:30 PM]
yep, will do
Travis Thompson  [2:30 PM]
thanks! great work everyone
Linear  [2:33 PM]
GitLab changed status to Done for PLAT-1974 DA COP submission missing for ERCOTAdded by Linear
Reply…Also send to alerts-platform-infraeng-build Buildkite Builds, Travis Thompson, and 2 othersBuildkite Builds  [11:50 AM]
[Failed] Tlaloc (master) #24167Merge branch 'lucas/miso_up_api_timeout' into 'master' - @Travis Thompson (875dbc3be2)
View BuildTlaloc master build failing! cc @platform-infra-oncall!Travis Thompson  [11:51 AM]
this is a weird one @Lucas Orts I don't see how this is related to the timeout change though
2026-07-09 11:50:19 PDT
	FAILED python/tlaloc/capa/tests/simulations/miso/dam/simulate_test.py::test_simulate_miso_day_ahead_market_reduced - AssertionError:
2026-07-09 11:50:19 PDT
	Not equal to tolerance rtol=0.01, atol=0.5
2026-07-09 11:50:19 PDT
	
2026-07-09 11:50:19 PDT
	Mismatched elements: 1 / 24 (4.17%)
2026-07-09 11:50:19 PDT
	Max absolute difference among violations: 2.99999287
2026-07-09 11:50:19 PDT
	Max relative difference among violations: 1.
2026-07-09 11:50:19 PDT
	 ACTUAL: array([3.      , 3.      , 3.      , 2.999991, 3.      , 0.      ,
2026-07-09 11:50:19 PDT
	       2.999991, 2.999991, 2.999991, 2.999991, 2.999991, 0.      ,
2026-07-09 11:50:19 PDT
	       0.      , 2.999991, 3.      , 3.      , 3.      , 3.      ,
2026-07-09 11:50:19 PDT
	       3.      , 3.      , 0.      , 0.      , 0.      , 0.      ])
2026-07-09 11:50:19 PDT
	 DESIRED: array([3.      , 3.      , 3.      , 2.999993, 3.      , 0.      ,
2026-07-09 11:50:19 PDT
	       2.999993, 2.999993, 2.999993, 2.999993, 2.999993, 2.999993,
2026-07-09 11:50:19 PDT
	       0.      , 2.999993, 3.      , 3.      , 3.      , 3.      ,
2026-07-09 11:50:19 PDT
	       3.      , 3.      , 0.      , 0.      , 0.      , 0.      ])
2026-07-09 11:50:19 PDT
	=================================================== 1 failed, 309 passed, 1 skipped, 706 warnings in 54.32s ====================================================
2026-07-09 11:50:21 PDT
	Exception ignored in: <function BaseComm.__del__ at 0x7ab872db7f60>
2026-07-09 11:50:21 PDT
	Traceback (most recent call last):
2026-07-09 11:50:21 PDT
	  File "/tlaloc/python/.venv/lib/python3.12/site-packages/comm/base_comm.py", line 82, in __del__
2026-07-09 11:50:21 PDT
	TypeError: 'NoneType' object is not callableLucas Orts  [12:01 PM]
yeah I don't think CAPA (market simulator code) should relate to the bid submission timeout at all. @Philippe, would you know if this is a flaky test?
Philippe  [12:02 PM]
hmmm I haven't seen that fail before but did make some changes recently to testdata so maybe it is now, looking into it
Travis Thompson  [12:04 PM]
I did also update protobuf yesterday, dunno if you're using protobuf encoded data, but ordering might have changed; but tests have been passing for the last ~18 hours
Philippe  [12:08 PM]
ah yeah this is the test that @Vrinda Vasavada had me and Anthony take a look at as well in the MR. Fails locally for me now though too.
Philippe  [12:09 PM]
(because in the MR it seemed the ordering was correctly updated)
Travis Thompson  [12:10 PM]
I thought so too
Philippe  [12:11 PM]
It does seem to be flaky now for some reason, it's both passing and failing for me locally.
Travis Thompson  [12:12 PM]
oh weird
Philippe  [12:13 PM]
will submit an MR with either a fix or a skip in a few
Philippe  [12:24 PM]
MR
Philippe  [1:15 PM]
welp think I found another one (test failed in CI of the MR)
Travis Thompson  [1:16 PM]
2026-07-09 13:06:09 PDT
	FAILED python/tlaloc/capa/tests/markets/resource_awards_test.py::TestResourcesOptimal::test_gen_resources_optimal_20230817_1900 - AssertionError: assert 'optimal_inaccurate' == 'optimal'
2026-07-09 13:06:09 PDT
	
2026-07-09 13:06:09 PDT
	  - optimal
2026-07-09 13:06:09 PDT
	  + optimal_inaccuratePhilippe  [1:17 PM]
yah looking
Travis Thompson  [1:17 PM]
love bugs that are non deterministic :melting_face:

Reply…Also send to eng-buildprod Matt Wytock, Lucas Orts, and 2 othersMatt Wytock  [7:26 AM]
MISO submission timed out but usually that means the bids are received. We should double check and perhaps adjust the interface by increasing the time out https://gridmatic.slack.com/archives/C03UH0LF97G/p1783519879994999
Triggered: Trading - bid model script failed on market:misoBid script miso/vesper_v18 failed.

Link to logs of pod

Link to trading reliability Dashboard

@slack-alerts-trading

1 event triggered this monitor, here is the last one.

 Tagsmarket:misoNotified@slack-alerts-tradingLucas Orts  [11:35 AM]
confirmed there's awards for tomorrow https://reports.gridmatic.com/stats/miso/awards/gmay/2026-07-09/
Matt Wytock  [8:25 AM]
MISO model bid submit failed for 3rd day in a row due to timeout. Even though the bids go through, I think its time to 2X the DART_TIMEOUT constant. Can you send an MR?
Matt Wytock  [8:26 AM]
If 2X doesn't work consistently then we can perhaps just swallow the timeout error and consider it a success or take some other measure but I think waiting longer for a success response would be best, as long as it comes eventually
Lucas Orts  [8:34 AM]
Yes, will send out MR today!
Lucas Orts  [10:11 AM]
Before doubling the DART_TIMEOUT value, I dug into why it's timing out and found that the failure isn't actually DART_TIMEOUT (900 sec) because the traceback shows it fails after ~60 sec. The timeout that's actually firing is MISO_API_TIMEOUT (default 60 sec), inside the new MISO interface API

@Victor, this 60 sec timeout didn't exist before this MR that separated out the MISO interface. The old interface service used httplib2 with no timeout set at all, so the only thing bounding a submission was the outer DART_TIMEOUT. Is the 60 sec HTTP timeout intentional (e.g. something the new httpx client needed), or can we just drop it / set it much higher so this matches prior behavior?

Side note: this also explains why it's not silently swallowed already. The existing "treat timeout as success" logic only catches DEADLINE_EXCEEDED, but this comes back as UNAVAILABLE (ReadTimeout), so it doesn't hit that path
Matt Wytock  [10:15 AM]
Ah good catch!
Victor  [10:20 AM]
yeah the timeout, as well as moving to httpx, was something we did for all of the new interface servers (edited) 
Victor  [10:23 AM]
this started before I joined, maybe @Dylan Larrabee or @Travis Thompson can comment?

afaik if we don't set a timeout it could just hang forever. we could make it longer though
Travis Thompson  [10:24 AM]
we can increase the timeout, but we should definitely have a timeout
Lucas Orts  [10:49 AM]
MR increasing internal timeout up from 60s to 400s

Reply…Also send to prodeng-build irene, Madeline Liao, and 3 othersirene  [5:09 PM]
The pipeline for a small MR keeps failing here, not sure if there is something I need to do on my side
Madeline Liao  [5:18 PM]
@platform-infra-oncall this is to get a fix to the ISONE DA cronjob in before tomorrow, ty for help!
Madeline Liao  [5:21 PM]
I also have an MR to tlaloc-env that’s hitting the same error
Eric Luxenberg  [5:32 PM]
same
Dylan Larrabee  [5:32 PM]
We're trying g to figure out the root cause. I the meantime I will keep restating your jobs until they work.
Dylan Larrabee  [5:37 PM]
eric what is the link to your job?
Eric Luxenberg  [5:39 PM]
https://gitlab.com/gridmatic/tlaloc-env/-/merge_requests/2504
Dylan Larrabee  [5:39 PM]
irene, it seems like the linting script cant run properly because it cant pull a needed schema from github - this seems to be an issue on the github server side that mey resove soon or may not. if it is urgent you can comment out the lint job from the gitlab-ci.yaml so CI passes
Dylan Larrabee  [5:40 PM]
yeah, same issue for both of you
Dylan Larrabee  [5:54 PM]
both pipelines are now green. we were getting rate limited by github for some data needed to run this check. I'm not sure why
Travis Thompson  [8:25 PM]
hm, I have setup a github api key for rate limiting reasons; we should look into mirroring that artifact though to get rid of the external dep, I've got another lint thing to fix up tomorrow I can take a look
Dylan Larrabee  [8:27 PM]
Specifically it was a tool called kubeconform that validates kube manifestes. It downloads schemas it uses for validation from a github CDN
Travis Thompson  [8:27 PM]
thanks for looking into it dylan, appreciate it
Dylan Larrabee  [8:28 PM]
Claude did suggest caching/mirroring, happy to work with you on  that. I feel like they probably don't change often (edited)