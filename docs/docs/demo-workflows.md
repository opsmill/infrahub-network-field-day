---
title: Service request workflows, through the portal and in Infrahub
description: Step-by-step instructions for the four service request workflows in the demo environment, each done once through the service portal and once by hand in the Infrahub UI, with what the proposed change shows and the problems to avoid.
audience: user
---

# Service request workflows, through the portal and in Infrahub

A branch user asks for a network service, Infrahub builds it on a branch, and a network engineer reviews and merges the proposed change. This page walks through four such requests. Each is done two ways:

- **Through the service portal.** The requester fills in a form, and the portal creates the branch, the service object and the proposed change.
- **By hand in the Infrahub UI.** The requester creates the branch, the service object and the proposed change themselves.

Both routes produce the same objects and the same configuration changes, so the second route shows what the portal does for the requester.

| Workflow | Service object | Portal template |
| --- | --- | --- |
| [Expose an application, with access](#expose-an-application-with-access) | `ServiceFabricApp` and `ServiceAppAccess` | Exposed application, with access |
| [Grant access to Grafana](#grant-access-to-grafana) | `ServiceAppAccess` | Application Access Grant |
| [Revoke access](#revoke-access) | `ServiceAppAccess`, status `decommissioning` | Revoke access |
| [Add a network segment](#add-a-network-segment) | `ServiceNetworkSegment` | Network Segment |

The steps and timings were recorded on the [demo environment without the lab](./setup-demo.md) on November 6, 2026. In that environment nothing is pushed to a device, so each workflow ends at the merge and the re-rendered configurations. In the [full lab](./setup-lab.md), the reconciler then pushes the merged configurations to the switches and the firewall; the [demo runbook](./demo-runbook.md) covers that part.

## Before you start

- **Accounts.** The requester is `alice@otternet.lab` (password `password`). Sign in to the portal at `https://localhost:32001` and to Infrahub at `http://localhost:8000` with **Sign in with Dex**. The network engineer who reviews and merges is the local account `alex`, with the password in `.env` as `INFRAHUB_NETWORK_ADMIN_PASSWORD`.
- **What a requester can and cannot do.** `alice` has the Requester Access role. She can create a branch, create and edit service objects on it, and open a proposed change. She cannot merge, rebase a branch, or change the groups of an object that already exists. The role is set by [`scripts/provision_requester_access.py`](https://github.com/opsmill/infrahub-network-field-day/blob/main/scripts/provision_requester_access.py).
- **A new branch can follow a merge straight away.** Artifacts keep rendering on `main` for about a minute after a merge, but the service generators no longer run there, so a branch cut in that minute passes its checks. See [A branch cut just after a merge failed its checks](#a-branch-cut-just-after-a-merge-failed-its-checks).
- **The portal session expires.** If a portal page shows **Login Required**, select **Log in**; the form keeps its values. If a running request's page stops updating, reload it and sign in again. The request keeps running in the background, and its proposed change still opens.

## Expose an application, with access

The requester asks for an application from the catalogue and access to it from the branch office. The result is one branch and one proposed change that hold the application, its access grant, the firewall rule, and the border leaf's new prefix-list line.

### Through the portal

1. In the portal, select **Create**, then **Choose** on **Exposed application, with access**.
2. On **The application**, fill in:

   | Field | Value used |
   | --- | --- |
   | Application name | `otter-shop` |
   | What it is | one sentence for someone who has never seen it |
   | Kubernetes namespace | `otter-shop`; leave empty to use the application name |
   | Owning organisation | `branch` (the default is `acme`) |
   | Application | **Who am I** |

   The **Application** picker lists the seven requestable catalogue entries: Podinfo, OTTERNET wiki, Grafana, Argo CD, n8n, OTTERNET shop, and the entry called Who am I. It does not ask for a chart, a version or an address block: those come from the catalogue entry.
3. Select **Next**. On **Who may reach it**, keep **Source site** at `branch-office`, write a reason in **Why**, and enter a **Request reference** such as `demo1`.
4. Select **Review**, check the summary, and select **Create**.

The task page lists four steps. **Build the application, its access and the fabric** runs eleven stages and logs each one; select the step to view the log. It took 94 seconds:

| Stage | Time |
| --- | --- |
| 1. Create the branch (`implement_otter-shop_demo1`) | 3 s |
| 2. Read the application's catalogue entry | under 1 s |
| 3. Create the application | 1 s |
| 4. Wait for the VIP block to be allocated | 31 s |
| 5–7. Read the block, check it exists, create the access grant | 1 s |
| 8. Wait for the firewall objects | 32 s |
| 9–10. Find the AVD generators, regenerate the host vars for every switch | 20 s |
| 11. Regenerate the structured configs | 5 s |

When it ends, the page links to **Review the proposed change**, **The application in Infrahub** and **The access grant in Infrahub**. The template is [`backstage/catalog/exposed-app-with-access.yaml`](https://github.com/opsmill/infrahub-network-field-day/blob/main/backstage/catalog/exposed-app-with-access.yaml).

### By hand in Infrahub

1. **Create a branch.** In the branch selector at the top left, select **+**, enter a name such as `implement_otter-shop-ui_demo2`, and select **Create a new branch**.
2. **Read the catalogue entry.** Open **Service Requests → Application Catalogue** and open **Who am I**. Note its chart repository (`https://cowboysysop.github.io/charts/`), chart name (`whoami`), chart version (`6.0.0`) and default service selector (`otternet.lab/advertise=true`). The UI does not copy these for you.
3. **Create the application.** On the new branch, open **Service Requests → Applications** and select **Add Fabric Application**. Fill in:

   | Field | Value used |
   | --- | --- |
   | Name, Description | `otter-shop-ui`, one sentence |
   | Owner | **Kind** `Tenant`, then `branch` |
   | Cluster | `otternet` |
   | Fabric Tenant VRF | `K8S_PROD` |
   | Catalogue Entry | **Who am I** |
   | Namespace | `otter-shop-ui` |
   | Chart Repository, Chart Name, Chart Version | the values from step 2 |
   | Exposed to Fabric | **True** |
   | Service Selector | `otternet.lab/advertise=true` |

   Fill **Service Selector** last. The field asks you to press Enter to add an item, and that Enter also saves the whole form.

   The **Catalogue Entry** picker in Infrahub lists all eleven entries, including the lab's own infrastructure entries that the portal hides. Pick a requestable one.
4. **Check that it was built.** Within about ten seconds, the application shows a **VIP Block** (for example `10.112.240.32/28`), **Pinned From Catalogue** is true, and **Advertised Services** lists `junos-http`. An event rule adds the application to the `service_fabric_apps` group and runs `generate-fabric-app`; you do not set the group yourself.
5. **Create the access grant.** Open **Service Requests → Application Access** and select **Add**. Fill in **Name** (`otter-shop-ui-access`), **Owner** (`Tenant`, `branch`), **Application** (`otter-shop-ui`), **Source Site** (`branch-office`), **Requester** (`alice@otternet.lab`) and **Justification**, then **Save**. Within a few seconds the grant's status is `active`, the firewall rule `svc-otter-shop-ui-access` exists, and `10.70.0.0/24` is added to the application's allowed source prefixes.
6. **Open the proposed change.** Switch the branch selector to `main`; **New proposed change** is disabled on any other branch. Open **Proposed Changes**, select **New proposed change**, choose the source branch, enter a name, and select **Open**.

You do not need to regenerate the switches' host vars by hand. When the grant's generator writes the border leaf's custom host vars, an event rule regenerates that leaf, and the proposed change's checks render the configuration.

### What the proposed change shows

Both routes produced the same proposed change, apart from names and addresses:

- **Checks:** 28, all successful, about 80 seconds after the change opened.
- **Artifacts:** six.
  - Added: the Crossplane FabricApp for the new application.
  - Updated: `fw1` Junos Configuration, the new rule and address-book entry.
  - Updated: `leaf-otternet-pod1-3-1` AVD EOS Configuration and AVD Device Documentation. The EOS diff is one added line in `PL-DC-ADVERTISED-BRANCH`, for example `seq 305420 permit 10.112.240.16/28`.
  - Updated: `otternet-dns` DNS Zone Configuration and `otternet-telegraf` Telemetry Collector Configuration.
- **Data:** the application, the grant, the VIP block, the firewall rule and its address-book entry, and the regenerated host vars.

A proposed change opened by the portal shows **Backstage portal** as its creator, and its description names the requester. One opened in the UI shows the requester.

## Grant access to Grafana

Grafana is the seeded application `otternet-metrics`. This workflow grants the branch office access to it.

### Through the portal

1. Select **Create**, then **Choose** on **Application Access Grant**.
2. Keep **What do you want to do?** on **Request a new service**. Fill in **Name** (`grafana-alice`), **Justification**, **Source Site** (`branch-office`), **Application** (`otternet-metrics`) and **Owner** (`branch`, typed). Leave **Permitted Ports** empty to use the application's advertised services.
3. Select **Review**, then **Create**.

The request took 48 seconds, 38 of them in **Wait for the generators**. It links to **Proposed change in Infrahub**.

### By hand in Infrahub

1. Create a branch, such as `implement_grafana-ui_demo4`.
2. Open **Service Requests → Application Access** and select **Add**. Fill in **Name** (`grafana-ui`), **Owner** (`Tenant`, `branch`), **Application** (`otternet-metrics`), **Source Site** (`branch-office`), **Requester** (`alice@otternet.lab`) and **Justification**, then **Save**.
3. Within about five seconds the rule `svc-grafana-ui` exists and the grant is `active`.
4. Switch to `main` and open a proposed change from the branch.

### What the proposed change shows

- **Checks:** 27, all successful.
- **Artifacts:** five: `fw1` Junos Configuration; the border leaf's EOS configuration and documentation, which gain `seq <n> permit 10.112.240.80/28`; the `otternet-metrics` Crossplane FabricApp, whose allowed sources gain the branch LAN; and the Telemetry Collector Configuration.

## Revoke access

Revoking sets a grant's status to `decommissioning` on a branch. The grant's generator then removes the firewall rule, the address-book entry and the source prefix the grant opened, and sets the status to `decommissioned`.

### Through the portal

1. Select **Create**, then **Choose** on **Revoke access**.
2. In **Grant to revoke**, pick the grant, for example `grafana-alice`. Write a reason in **Why** and enter a **Request reference** such as `demo3`.

   The picker lists grants from the portal's catalogue, which reads Infrahub's `main`. A grant merged in the last few minutes may not be listed yet; reload the page after a few minutes.
3. Select **Review**, then **Create**.

The request took about 75 seconds: 38 seconds waiting for the firewall objects to be removed, then 32 seconds regenerating the switches' host vars and structured configs. It links to **Review the revocation**. The template is [`backstage/catalog/revoke-access.yaml`](https://github.com/opsmill/infrahub-network-field-day/blob/main/backstage/catalog/revoke-access.yaml).

### By hand in Infrahub

1. Create a branch, such as `revoke_grafana-ui_demo6`.
2. On that branch, open the grant (**Service Requests → Application Access**, then the grant), select **Edit**, set **Status** to **Decommissioning**, and select **Save**.
3. Within a few seconds the rule is removed, `10.70.0.0/24` is removed from the application's allowed sources, and the status reads `decommissioned`.
4. Wait about a minute for the border leaf's host vars to regenerate, then switch to `main` and open a proposed change from the branch.

### What the proposed change shows

- **Checks:** 27, all successful.
- **Artifacts:** the same five as the grant. The border leaf's EOS diff removes the grant's `permit` line.
- **Data:** the grant's status change and the removed rule and address-book entry.

After the merge, the grant stays on `main` with status `decommissioned`. It configures nothing, but the Revoke access picker still lists it.

## Add a network segment

A network segment is a subnet, a VLAN and a gateway (SVI) for a tenant, allocated from pools. See also [Add a network segment](./how-to/add-network-segment.md).

### Through the portal

1. Select **Create**, then **Choose** on **Network Segment**.
2. Fill in:

   | Field | Value used |
   | --- | --- |
   | Prefix Length | `24` (the default) |
   | VLAN ID | empty, to take the next free ID from the pool |
   | Name, Description | `acme-web`, one sentence |
   | VRF | `TENANT_ACME`, typed; it must already exist |
   | Tenant | `acme`, typed |
   | AVD Tags | select **+** and enter `app`; the tag must match a rack's tags (`app`, `cloud`, `border` or `k8s`) or the segment renders on no switch |
   | Fabric | `OTTERNET_FABRIC` |
   | Owner | `acme` |

3. Select **Review**, then **Create**.

The request took 40 seconds. The generator allocated `10.230.0.0/24` and created the VLAN and the SVI, both named `acme-web`.

### By hand in Infrahub

1. Create a branch, such as `implement_acme-api_demo7`.
2. Open **Service Requests → Network Segments** and select **Add**. Fill in **Name** and **Description**, **Owner** (`Tenant`, `acme`), **Tenant** (`acme`), **VRF** (`TENANT_ACME`), **Fabric** (`OTTERNET_FABRIC`) and **AVD Tags** (`app`), then **Save**. The **SVI** section shows a **VRF** value; it only filters the SVI picker, which stays empty.

   If you cancel the form, reload the page before you select **Add** again. A reopened form keeps the earlier values, and typing adds to them.
3. Within about five seconds the segment has a subnet (`10.230.1.0/24`), a VLAN and an SVI, and its status is `active`.
4. Switch to `main` and open a proposed change from the branch.

### What the proposed change shows

- **Checks:** 17 when nothing else has changed on `main`, all successful.
- **Artifacts:** five: the AVD EOS Configuration and AVD Device Documentation of `leaf-otternet-pod1-2-1` and `leaf-otternet-pod1-2-2`, the two leaves of the `APP_LEAFS` rack, and the Telemetry Collector Configuration.

## Review and merge

The network engineer signs in to Infrahub as `alex`, opens the proposed change, and checks three tabs:

- **Checks:** every check is successful.
- **Artifacts:** only the expected devices changed, in the expected way.
- **Data:** the service object and the objects its generator built.

Then select **Merge**. Each merge took 14 to 23 seconds.

## Problems found while testing

### A branch cut just after a merge failed its checks

Two manual tests cut a branch within about a minute of the previous merge. Both proposed changes failed a check:

- **Revoke access:** **Data Integrity** failed with a conflict on the grant's address-book prefix (`svc-grafana-ui-vip`), updated on `main` after the branch was cut and removed on the branch. Infrahub refused both a rebase and a conflict resolution, so the branch had to be deleted and the revoke made again.
- **Network segment:** **Generator Validator: generate-network-segment** failed with `Please rebase this branch`. `alice` cannot rebase (the **Rebase** button returns an error 403); a network engineer's rebase fixed it.

The cause was that `generate-app-access`, `generate-network-segment`, `generate-tenant-onboarding` and `generate-server-placement` ran again on `main` after every merge, for every service they target, which is Infrahub's default. Those runs rewrote objects on `main` that a new branch also touched. The four services are built on their branch and checked in the proposed change, so the run on `main` added nothing. [`.infrahub.yml`](https://github.com/opsmill/infrahub-network-field-day/blob/main/.infrahub.yml) now sets `execute_after_merge: false` for them.

With that setting, a segment request and a revoke cut 6 seconds after a merge passed all their checks: 17 and 27. With the old setting, the same test failed both.

An existing stack needs one migration step, because the generators then keep their records in a `CoreGeneratorAwareGroup` instead of a `CoreGeneratorGroup` with the same name: delete the `CoreGeneratorGroup` groups named `generate-app-access-…`, `generate-network-segment-…`, `generate-tenant-onboarding-…` and `generate-server-placement-…` on `main`. A stack built with `uv run invoke bootstrap --fresh` does not need it.

### A service created in the UI was not built

Before this page was written, only access grants were added to their generator's group automatically. An application or a network segment created in the UI without setting **Member Of Groups** was never built, and `alice` could not add the group afterwards: **Save** in the **Groups** dialog did nothing, and the browser console showed `PERMISSION_DENIED` for `object:Core:StandardGroup:update`. [`triggers.yml`](https://github.com/opsmill/infrahub-network-field-day/blob/main/triggers.yml) now adds every service kind to its generator's group when it is created, whichever client creates it.
