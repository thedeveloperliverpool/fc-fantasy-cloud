using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class UIManager : MonoBehaviour
{
    private Canvas canvas;
    private Text scoreText;
    private Text timeText;
    private Text commentaryText;
    private GameObject pausePanel;

    private Text menuText;
    private Text hubText;
    private Text tableText;
    private Text transfersText;
    private Text lineupText;

    private RectTransform miniMap;
    private RectTransform miniBall;
    private List<RectTransform> miniHome = new List<RectTransform>();
    private List<RectTransform> miniAway = new List<RectTransform>();

    private readonly Queue<string> commentaryQueue = new Queue<string>();
    private float commentaryTimer = 0f;

    public void BuildUI()
    {
        canvas = new GameObject("HUD").AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 100;
        var scaler = canvas.gameObject.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);
        canvas.gameObject.AddComponent<GraphicRaycaster>();

        var topBar = new GameObject("TopBar");
        topBar.transform.SetParent(canvas.transform, false);
        var topImage = topBar.AddComponent<Image>();
        topImage.color = new Color(0f, 0f, 0f, 0.45f);
        var topRect = topBar.GetComponent<RectTransform>();
        topRect.anchorMin = new Vector2(0f, 1f);
        topRect.anchorMax = new Vector2(1f, 1f);
        topRect.sizeDelta = new Vector2(0, 80);
        topRect.anchoredPosition = new Vector2(0, 0);

        scoreText = CreateText("ScoreText", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0, 10), 28, TextAnchor.MiddleCenter, topBar.transform);
        timeText = CreateText("TimeText", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0, -18), 22, TextAnchor.MiddleCenter, topBar.transform);
        commentaryText = CreateText("CommentaryText", new Vector2(0f, 0f), new Vector2(0f, 0f), new Vector2(20, 20), 18, TextAnchor.LowerLeft, canvas.transform);

        menuText = CreateText("MenuText", new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(20, -100), 20, TextAnchor.UpperLeft, canvas.transform);
        hubText = CreateText("HubText", new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(20, -100), 20, TextAnchor.UpperLeft, canvas.transform);
        tableText = CreateText("TableText", new Vector2(1f, 1f), new Vector2(1f, 1f), new Vector2(-20, -100), 18, TextAnchor.UpperRight, canvas.transform);
        transfersText = CreateText("TransfersText", new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(20, -100), 18, TextAnchor.UpperLeft, canvas.transform);
        lineupText = CreateText("LineupText", new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(20, -100), 18, TextAnchor.UpperLeft, canvas.transform);

        pausePanel = new GameObject("PausePanel");
        pausePanel.transform.SetParent(canvas.transform, false);
        var panelImage = pausePanel.AddComponent<Image>();
        panelImage.color = new Color(0f, 0f, 0f, 0.6f);
        var panelRect = pausePanel.GetComponent<RectTransform>();
        panelRect.anchorMin = new Vector2(0f, 0f);
        panelRect.anchorMax = new Vector2(1f, 1f);
        panelRect.offsetMin = Vector2.zero;
        panelRect.offsetMax = Vector2.zero;
        var pauseText = CreateText("PauseText", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, 28, TextAnchor.MiddleCenter, pausePanel.transform);
        pauseText.text = "PAUSED";
        pausePanel.SetActive(false);

        BuildMiniMap();
        ShowCareerPanels(true);
    }

    public void ShowCareerPanels(bool show)
    {
        menuText.gameObject.SetActive(show);
        hubText.gameObject.SetActive(show);
        tableText.gameObject.SetActive(show);
        transfersText.gameObject.SetActive(show);
        lineupText.gameObject.SetActive(show);
    }

    private void BuildMiniMap()
    {
        var mapObj = new GameObject("MiniMap");
        mapObj.transform.SetParent(canvas.transform, false);
        miniMap = mapObj.AddComponent<RectTransform>();
        var mapImage = mapObj.AddComponent<Image>();
        mapImage.color = new Color(0.05f, 0.2f, 0.08f, 0.85f);
        miniMap.anchorMin = new Vector2(1f, 0f);
        miniMap.anchorMax = new Vector2(1f, 0f);
        miniMap.sizeDelta = new Vector2(180, 110);
        miniMap.anchoredPosition = new Vector2(-20, 20);

        miniBall = CreateDot("BallDot", Color.white);
        miniBall.transform.SetParent(miniMap, false);
    }

    private RectTransform CreateDot(string name, Color color)
    {
        var go = new GameObject(name);
        var img = go.AddComponent<Image>();
        img.color = color;
        var rt = go.GetComponent<RectTransform>();
        rt.sizeDelta = new Vector2(6, 6);
        return rt;
    }

    private Text CreateText(string name, Vector2 anchorMin, Vector2 anchorMax, Vector2 anchoredPos, int size, TextAnchor align, Transform parent)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var text = go.AddComponent<Text>();
        text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        text.fontSize = size;
        text.alignment = align;
        text.color = Color.white;
        var rect = text.GetComponent<RectTransform>();
        rect.anchorMin = anchorMin;
        rect.anchorMax = anchorMax;
        rect.anchoredPosition = anchoredPos;
        rect.sizeDelta = new Vector2(800, 200);
        return text;
    }

    public void BindMiniMap(List<PlayerController> home, List<PlayerController> away)
    {
        foreach (var dot in miniHome) Destroy(dot.gameObject);
        foreach (var dot in miniAway) Destroy(dot.gameObject);
        miniHome.Clear();
        miniAway.Clear();

        foreach (var _ in home)
        {
            var dot = CreateDot("HomeDot", new Color(0.2f, 0.6f, 1f));
            dot.transform.SetParent(miniMap, false);
            miniHome.Add(dot);
        }
        foreach (var _ in away)
        {
            var dot = CreateDot("AwayDot", new Color(1f, 0.3f, 0.3f));
            dot.transform.SetParent(miniMap, false);
            miniAway.Add(dot);
        }
    }

    public void UpdateMiniMap(List<PlayerController> home, List<PlayerController> away, BallController ball)
    {
        for (int i = 0; i < home.Count && i < miniHome.Count; i++)
        {
            miniHome[i].anchoredPosition = WorldToMini(home[i].transform.position);
        }
        for (int i = 0; i < away.Count && i < miniAway.Count; i++)
        {
            miniAway[i].anchoredPosition = WorldToMini(away[i].transform.position);
        }
        miniBall.anchoredPosition = WorldToMini(ball.transform.position);
    }

    private Vector2 WorldToMini(Vector3 pos)
    {
        float x = (pos.x / GameConfig.FieldWidth) * miniMap.sizeDelta.x;
        float y = (pos.z / GameConfig.FieldLength) * miniMap.sizeDelta.y;
        return new Vector2(x, y);
    }

    public void SetScore(int home, int away)
    {
        scoreText.text = $"HOME {home} - {away} AWAY";
    }

    public void SetTime(float seconds)
    {
        int min = Mathf.FloorToInt(seconds / 60f);
        int sec = Mathf.FloorToInt(seconds % 60f);
        timeText.text = $"{min:00}:{sec:00}";
    }

    public void AddCommentary(string line)
    {
        commentaryQueue.Enqueue(line);
    }

    public void TickCommentary(float dt)
    {
        if (commentaryTimer > 0f)
        {
            commentaryTimer -= dt;
            return;
        }
        if (commentaryQueue.Count > 0)
        {
            commentaryText.text = commentaryQueue.Dequeue();
            commentaryTimer = 2.0f;
        }
    }

    public void SetPaused(bool paused)
    {
        pausePanel.SetActive(paused);
    }

    public void SetMenuText(string text) => menuText.text = text;
    public void SetHubText(string text) => hubText.text = text;
    public void SetTableText(string text) => tableText.text = text;
    public void SetTransfersText(string text) => transfersText.text = text;
    public void SetLineupText(string text) => lineupText.text = text;
}
