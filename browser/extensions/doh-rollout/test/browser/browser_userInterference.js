"use strict";

add_task(async function testUserInterference() {
  // Set up a passing environment and enable DoH.
  setPassingHeuristics();
  let promise = waitForDoorhanger();
  Preferences.set(prefs.DOH_ENABLED_PREF, true);

  await BrowserTestUtils.waitForCondition(() => {
    return Preferences.get(prefs.DOH_SELF_ENABLED_PREF);
  });
  is(Preferences.get(prefs.DOH_SELF_ENABLED_PREF), true, "Breadcrumb saved.");

  let panel = await promise;
  is(
    Preferences.get(prefs.DOH_DOORHANGER_SHOWN_PREF),
    undefined,
    "Doorhanger shown pref undefined before user interaction."
  );

  // Click the doorhanger's "accept" button.
  let button = panel.querySelector(".popup-notification-primary-button");
  promise = BrowserTestUtils.waitForEvent(panel, "popuphidden");
  EventUtils.synthesizeMouseAtCenter(button, {});
  await promise;

  await BrowserTestUtils.waitForCondition(() => {
    return Preferences.get(prefs.DOH_DOORHANGER_SHOWN_PREF);
  });

  is(
    Preferences.get(prefs.DOH_DOORHANGER_SHOWN_PREF),
    true,
    "Doorhanger shown pref saved."
  );
  is(
    Preferences.get(prefs.DOH_DOORHANGER_USER_DECISION_PREF),
    "UIOk",
    "Doorhanger decision saved."
  );

  await ensureTRRMode(2);

  // Set the TRR mode pref manually and ensure we respect this.
  Preferences.set(prefs.TRR_MODE_PREF, 0);

  // Simulate a network change.
  simulateNetworkChange();
  await ensureNoTRRModeChange(0);

  is(
    Preferences.get(prefs.DOH_DISABLED_PREF, false),
    true,
    "Manual disable recorded."
  );
  is(
    Preferences.get(prefs.DOH_SELF_ENABLED_PREF),
    undefined,
    "Breadcrumb cleared."
  );

  // Simulate another network change.
  simulateNetworkChange();
  await ensureNoTRRModeChange(0);

  // Restart the add-on for good measure.
  await restartAddon();
  await ensureNoTRRModeChange(0);

  // Simulate another network change.
  simulateNetworkChange();
  await ensureNoTRRModeChange(0);

  // Clean up.
  await resetPrefsAndRestartAddon();
});
