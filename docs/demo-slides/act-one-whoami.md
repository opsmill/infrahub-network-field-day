# Demo act one: requesting the Who am I application

This page describes, step by step, what happens when a branch-office user requests the **Who am I** application through the service portal. It is the script behind the animated slides in [act-one-whoami.html](./act-one-whoami.html).

## TL;DR

- **Problem:** A branch-office user wants to reach a new application in the Kubernetes data center. Today that means a ticket to the application team, a second ticket to the network team, a third to the firewall team, and a fourth to a reviewer.
- **What act one shows:** One request in the portal produces one proposed change in Infrahub. The proposed change holds the application, the firewall rule that permits it, the border leaf configuration that advertises it, and the monitoring for both. A reviewer merges once, and the application answers the user's packet about 70 seconds later.
- **Not decided yet:** Which of the slide designs in [Slide designs](#slide-designs) the presenter wants. Whether the slides replace or sit beside the live portal is not known from the sources.

## Sources

Every statement of fact below comes from these files in this repository. Timings are the measured values recorded in the runbook.

- [Demo runbook, act one](../docs/demo-runbook.md#act-one-ask-for-an-application)
- [Demo runbook, presenter run sheet](../docs/demo-runbook.md#presenter-run-sheet-from-a-freshly-bootstrapped-lab)
- [Service portal](../docs/service-portal.md)
- [Portal template: Exposed application, with access](../../backstage/catalog/exposed-app-with-access.yaml)

Text labelled `[CLAUDE RECOMMENDED – based on X]` is a suggestion and is not in a source.

## The people and systems in the story

| Name | Role in act one |
| --- | --- |
| `alice@otternet.lab` | The branch-office user who requests the application. Signs in to the portal through Dex. |
| Service portal | The Backstage portal in the tooling cluster. Alice fills in one form. |
| Application catalogue | The platform team's list of applications, held in Infrahub as `ServiceApplicationDefinition` nodes. Decides the chart, version, ports, block size and values. |
| Infrahub | Holds the intent. Alice's request becomes nodes on a branch. |
| Generators | Build the technical nodes from the request: the VIP block, the firewall rule, the switch configuration. |
| Reviewer | The person who reads the proposed change and merges it. Merging is the approval. |
| Vidra | Delivers the merged application to the Kubernetes cluster. |
| Deployment reconciler | Pushes the merged configuration to the firewall and the border leaf, then confirms it. |
| `fw1`, `leaf-otternet-pod1-3-1` | The firewall and the border leaf that change. The other six switches do not change. |

## Step 1: Alice asks (0 s)

Alice opens the portal on the branch desktop, signs in as `alice@otternet.lab`, and chooses the template **Exposed application, with access**.

She fills in five fields:

| Field | Value in the demo |
| --- | --- |
| Application name | `otter-shop` |
| What it is | A description a stranger would understand |
| Kubernetes namespace | `otter-shop` |
| Application | **Who am I**, picked from a list |
| Request reference | `demo1`, or any reference not used before |

The defaults are the cluster `otternet`, the VRF `K8S_PROD` and the source site `branch-office`.

**What Alice does not see or decide:** the chart repository, chart version, ports, block size, selector and values. The catalogue entry for Who am I decides them: chart `whoami` 6.0.0, a `/28` VIP block, the `junos-http` service, and values with a LoadBalancer Service carrying the label `otternet.lab/advertise: "true"`.

**What the picker hides:** the lab's own Grafana, Prometheus and Telegraf are catalogue entries too, but they are not requestable, so they do not appear in the list.

Source: [runbook, step 1 Ask](../docs/demo-runbook.md#act-one-ask-for-an-application), [service portal, catalogue](../docs/service-portal.md#exposed-application-with-access).

## Step 2: The portal runs four steps (0 to about 80 s)

The task page shows four steps. The run takes 70 to 85 seconds, and most of that is two waits.

| Portal step | What it does |
| --- | --- |
| 1. Look up the application | Resolves the picked catalogue entry to its Infrahub id. |
| 2. Build the application, its access and the fabric | The long step. Runs eleven stages in a fixed order and writes one numbered log line for each. |
| 3. Open the proposed change | Runs only if step 2 finished. |
| 4. Refresh the catalogue | Lists the new services when the run ends. |

### The eleven stages inside portal step 2

Clicking the step opens its log. Each stage writes a line such as `3/11 Create the application`, then `3/11 Create the application: done in 1.2s`. A failure names the stage and gives Infrahub's own error.

| Stage | Name in the log | What it means for Alice's request |
| --- | --- | --- |
| 1 | Create the branch | Infrahub makes the branch `implement_otter-shop_demo1`. Nothing on `main` changes. |
| 2 | Read the application's catalogue entry | Reads the entry again, with the same two conditions the picker used (requestable and active). A stale form cannot request an entry that was withdrawn. |
| 3 | Create the application | Creates the `ServiceFabricApp` on the branch as `alice`, with the entry's chart and version. The write carries her account, so Infrahub attributes it to her and not to the portal's service account. |
| 4 | Wait for the VIP block to be allocated | The application's generator takes a `/28` block from the cluster's pool. |
| 5 | Read the allocated block | Reads which block was allocated. |
| 6 | Prove the block exists before granting access to it | Stops the run if the block is missing, before the grant is created. |
| 7 | Create the access grant | Creates the `ServiceAppAccess` with Alice as requester. |
| 8 | Wait for the firewall objects | The grant's generator creates the firewall rule, the address-book entry and the allowed source prefix. |
| 9 | Find the AVD generators | Locates the two generators that render switch data. |
| 10 | Regenerate the host vars for every switch | Rebuilds the host vars for all seven switches. |
| 11 | Regenerate the structured configs | Rebuilds the structured configuration for all seven switches. Stages 10 and 11 together take 21 to 25 seconds. |

Why the order matters:

- **Stages 4 to 6 exist because of a race.** The grant's generator reads the application's VIP block, and the application's generator allocates it. Both start when their node is created and nothing else orders them. A grant created before the block exists is stamped `error`, and nothing retries it until someone edits one of the grant's own inputs. The run therefore waits for the block, then proves it exists, then creates the grant.
- **Stages 10 and 11 exist so the reviewer sees configuration.** Without regenerating the fabric, the border leaf's change would be a JSON attribute changing instead of a configuration line.
- **The proposed change opens only after all eleven stages.** Its checks then render from current data.

Source: [runbook, what to say while step 2 runs](../docs/demo-runbook.md#act-one-ask-for-an-application), [portal template stages](../../backstage/catalog/exposed-app-with-access.yaml).

## Step 3: The reviewer reads one proposed change (about 80 s, then 60 to 80 s while validators run)

The run ends at a **Review the proposed change** link. The proposed change holds everything the request needs, in one place:

| Group | Contents |
| --- | --- |
| Service nodes | The `ServiceFabricApp`, and the `ServiceAppAccess` with `alice@otternet.lab` as requester. |
| Address allocation | The VIP block taken from the cluster's pool. |
| Firewall | The rule `svc-otter-shop-access` (`branch` to `k8s-prod`, service `junos-http`), its address-book entry for the VIP, and `10.70.0.0/24` added to the application's own allowed sources (the pod-level gate). |
| Switch configuration | Regenerated host vars, and one rendered configuration line on `leaf-otternet-pod1-3-1`: `seq <n> permit <vip block>` in `PL-DC-ADVERTISED-BRANCH`. The other six switches are unchanged. |
| Rendered artifacts | The re-rendered **Junos Configuration** for `fw1`, the **Crossplane FabricApp** artifact for the new application, and the **Telemetry Collector Configuration**. |

The telemetry artifact gains checks that nobody asked for: the application's pods ready and its VIP assigned, and the grant's rule on a confirmed `fw1`. A monitoring profile watches every service of a kind, so new services are watched without a request.

**Validators.** The proposed change reaches 24 validators, all green, after a further 60 to 80 seconds. The checks named in the runbook are `wan-service-consistency`, `zone-advertisement`, `allocation-consistency`, `peering-consistency` and `fabric-pool-validation`.

**OTTERNET / Services dashboard.** While the proposed change is open, both new services are listed at **Requested**, with the branch, the proposed change and the validators' verdict (**Running**, then **Passed**). A request whose validators fail turns **Validators failing** and **Stalled** red here before anyone opens the proposed change.

**Merging is the approval.** The grant has no second gate, on purpose: two gates can only disagree.

Source: [runbook, step 2 Read the proposed change](../docs/demo-runbook.md#act-one-ask-for-an-application).

## Step 4: The reviewer merges (about 160 s from the request)

The merge call takes 15 to 22 seconds. From here the clock below counts from the merge.

## Step 5: Vidra delivers the application to the cluster (merge to about 100 s)

Vidra delivers the merged `FabricApp` within about a minute.

| Time after merge | What the presenter can show |
| --- | --- |
| About 40 s | The Service has an external IP, which is the VIP inside the allocated block. |
| About 100 s | `kubectl get fabricapp otter-shop` shows `READY True`. |

Commands:

```bash
kubectl get fabricapp otter-shop                 # SYNCED True, READY True
kubectl -n otter-shop get svc                    # EXTERNAL-IP is the VIP, inside the allocated block
```

## Step 6: The reconciler pushes two devices and confirms them (merge to about 146 s)

Once the merged artifacts have re-rendered and held still for two polls, the deployment reconciler starts a cycle without waiting out its interval.

| Time after merge | What happens |
| --- | --- |
| About 40 s | The border leaf changes. |
| About 55 s | `fw1` changes. |
| About 146 s | A confirmation cycle finds `differed=0`. |

If nothing has moved after two minutes, the runbook gives `uv run invoke reconcile --now`.

How the two pushes stay safe:

- **Both pushes are full replaces, never merges.**
- **The border leaf** is changed in an EOS configuration session that starts from `rollback clean-config`.
- **The firewall** loads the whole artifact with `load override` and commits it with `commit confirmed`. The reconciler sends the confirmation only once the device still answers, so a push that cut the reconciler off rolls itself back.

**Deployment state dashboard.** It shows each device as `pending` between the push and the confirming comparison, and `in_sync` only when a later comparison finds no difference. Green means the device said it matches. It never means something was only sent. The dashboard lags the log by up to two minutes, so the runbook advises narrating from the log and using the dashboard to show the end state.

Source: [runbook, step 4 Then the devices](../docs/demo-runbook.md#act-one-ask-for-an-application).

## Step 7: The packet (merge to about 70 s for the first answer)

From the branch desktop:

```bash
docker exec clab-otternet-branch-desktop curl -s -m 10 http://<otter-shop vip>/     # whoami answers
docker exec clab-otternet-branch-desktop curl -s -m 8 http://10.112.240.0/          # times out
```

The second command matters more than the first. The application `otternet-demo` is running, advertised and healthy, and the branch still cannot reach it. This shows the firewall rule and the pod policy are the control, and not an open path.

## Step 8: The services turn green

On OTTERNET / Services, both rows move from **Requested** to **Merged** within a minute of the merge. They move to **Deployed** once the reconciler has confirmed every device since. Deployed means confirmed, never merely pushed. **Healthy** counts them once their checks pass. A purple **created** annotation marks when each reached `main`, and a green one marks the merge.

## Timeline

| Elapsed | Event | Source |
| --- | --- | --- |
| 0 s | Alice submits the request | [runbook](../docs/demo-runbook.md#act-one-ask-for-an-application) |
| 70 to 85 s | The run ends at the Review link | [run sheet](../docs/demo-runbook.md#presenter-run-sheet-from-a-freshly-bootstrapped-lab) |
| plus 60 to 80 s | 24 validators are green | run sheet |
| plus 15 to 22 s | Merge call returns | run sheet |
| Merge plus about 40 s | The Service has an external IP; the border leaf changes | run sheet, runbook |
| Merge plus about 55 s | `fw1` changes | runbook |
| Merge plus about 70 s | whoami answers the branch desktop | run sheet |
| Merge plus about 100 s | `FabricApp` is `READY True` | run sheet |
| Merge plus about 146 s | The reconciler confirms both devices | run sheet |

Total measured for act one: 321 to 342 seconds. Planned time on screen: about 5 minutes.

## Slide designs

The file [act-one-whoami.html](./act-one-whoami.html) holds ten slides. Press the right arrow key or click to reveal the next animation step; press the left arrow key to go back. Press `P` to play the whole sequence automatically. The animations are plain CSS and respect the reduced-motion setting.

| Slide | Title | Animation | What the audience learns |
| --- | --- | --- | --- |
| 1 | One request | The form fields type in; five fields appear, then a greyed-out group labelled "decided by the platform team" fades in. | Alice states what she wants and nothing about how. |
| 2 | Four steps on the task page | Four step cards turn from grey to blue to green in order, with a running timer. | The portal shows progress in four steps. |
| 3 | Eleven stages in step 2 | A log scrolls: each line shows "started", then a green tick and its duration. Stages 4 to 6 are highlighted as "waits for the VIP block". | What the portal does in order, and why the order matters. |
| 4 | A branch, not `main` | Two lanes. A new lane `implement_otter-shop_demo1` branches off `main`, and nodes drop onto it: application, VIP block, grant, firewall rule. | Nothing touches `main` until a reviewer merges. |
| 5 | One proposed change | Five cards slide in: service nodes, address allocation, firewall, border leaf (one line), artifacts. A counter climbs to 24 validators and turns green. | A single change holds every part of the request. |
| 6 | The reviewer merges | A button press, a 15 to 22 s merge ring, and the branch lane joins `main`. | Merging is the approval. |
| 7 | Delivery to the cluster | Two arrows leave `main`: one to Kubernetes, one to the reconciler. Kubernetes shows the Service gaining an external IP at 40 s and `READY True` at 100 s. | Vidra delivers the application. |
| 8 | Two devices, then confirmation | Fourteen device dots. Two (`fw1`, the border leaf) turn amber for `pending`, then green for `in_sync` after the confirming cycle. | Green means confirmed, not sent. |
| 9 | The packet | Two packets leave the branch desktop. One crosses the firewall and returns "whoami". The other stops at the firewall with a timeout. | The firewall rule is the control. |
| 10 | Timeline | A horizontal bar fills with the eleven measured events. | The full request takes about five minutes. |

[CLAUDE RECOMMENDED – based on the runbook note that the dashboard lags the log by up to two minutes] Drive slide 8 from the reconciler log and not from Grafana, so the animation does not run ahead of or behind what the audience sees.

[CLAUDE RECOMMENDED – based on the runbook's 70 to 85 second idle wait during portal step 2] Show slide 3 while the real task log runs, so the audience reads the explanation while the live stages tick.

## Not known from the sources

- Whether the slides will be shown in a browser, exported to PDF or rebuilt in another presentation tool.
- The wording the presenter wants for the audience, in particular whether the term "VIP block" needs a definition for a non-network audience.
- The timings for the Argo CD application and other catalogue entries differ from Who am I. See [the other catalogue applications](../docs/demo-runbook.md#the-other-catalogue-applications).
