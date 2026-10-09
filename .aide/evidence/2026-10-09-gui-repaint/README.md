A contained GUI diagnosis at repository base `5d8803220f9231073f94276e57145f8955a828c5` used the clean
dev.31 artifact from source `1f80711f9bfe9d8a18a1cf92878f98a117c8f0d9`. Exact executable SHA-256:
`sha256:ed8129d675d3187209120ed05bf3a0c2973b08534c9a1e75239b3123823ff315`. This is implementing-agent observation, not owner acceptance.

The shared capture helper accepted before.png even though only the window frame
was painted. The native submit control's exact text was `&Submit reviewed` and
the reviewed control was enabled. An owned-window RedrawWindow call with flags
0x585 produced after.png with the visible caption and full client content. The
review data and caption remained identical; no request was submitted and no case
or output path was accessed. Actual control/process exit results are in result.json.
The before/after images were inspected directly; no image was edited or generated.

This establishes an observed capture/repaint problem on the tested unelevated
Windows host. It does not prove every GUI frame, caption, DPI or other platform.
No runtime source or shared fixture was repaired by this diagnosis. Implement
bounded owned-window redraw and a client-content check in the screenshot helper;
the existing whole-window color-count check can accept a frame-only false positive.
Retain both failed and corrected captures when qualifying that repair.

probe.py retains the exact diagnostic. It requires the existing selected artifact,
retained product-export sample and installed Python environment. It refuses an
existing owned diagnostic directory; use a fresh checkout/path for reproduction.
The execution grant covers local fake/generated-file development only. Owner,
physical/customer/elevation/install/signing/publication/release gates stay separate.
