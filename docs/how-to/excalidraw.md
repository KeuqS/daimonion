# How to embed Excalidraw diagrams

Start off by creating your diagram at [excalidraw.com](https://excalidraw.com).

Click 'Save as image' and make sure the 'Embed scene' checkbox is enabled. This is required for loading your image back into Excalidraw should you wish to make changes later on. Name your file and export to SVG, saving it inside `docs/images`.

Add the following to embed it inside your documentation:

```markdown
![Excalidraw Diagram](../images/excalidraw-example.svg)
```

Rebuild the docs (`task docs`) and open the resulting HTML inside a browser.
