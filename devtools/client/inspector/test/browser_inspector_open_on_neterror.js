/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
"use strict";

// Test that inspector works correctly when opened against a net error page

const TEST_URL_1 = "http://127.0.0.1:36325/";
const TEST_URL_2 = "data:text/html,<html><body>test-doc-2</body></html>";

add_task(async function() {
  // Unfortunately, net error page are not firing load event, so that we can't
  // use addTab helper and have to do that:
  const tab = (gBrowser.selectedTab = BrowserTestUtils.addTab(
    gBrowser,
    "data:text/html,empty"
  ));
  await BrowserTestUtils.browserLoaded(tab.linkedBrowser);
  await SpecialPowers.spawn(
    tab.linkedBrowser,
    [{ url: TEST_URL_1 }],
    async function({ url }) {
      // Also, the neterror being privileged, the DOMContentLoaded only fires on
      // the chromeEventHandler.
      const { chromeEventHandler } = docShell; // eslint-disable-line no-undef
      const onDOMContentLoaded = ContentTaskUtils.waitForEvent(
        chromeEventHandler,
        "DOMContentLoaded",
        true
      );
      content.location = url;
      await onDOMContentLoaded;
    }
  );

  const { inspector, testActor } = await openInspector();
  ok(true, "Inspector loaded on the already opened net error");

  const documentURI = await testActor.eval("document.documentURI;");
  ok(
    documentURI.startsWith("about:neterror"),
    "content is really a net error page."
  );

  info("Navigate to a valid url");
  await navigateTo(inspector, TEST_URL_2);

  is(
    await getDisplayedNodeTextContent("body", inspector),
    "test-doc-2",
    "Inspector really inspects the valid url"
  );
});
