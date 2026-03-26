using System;
using System.Collections.Generic;
using UnityEngine;

[Serializable]
public class TeamDatabase
{
    public List<TeamEntry> teams = new List<TeamEntry>();

    [Serializable]
    public class TeamEntry
    {
        public string name;
        public int rating_base;
        public int overall;
        public string stadium;
        public List<KitEntry> kits;
        public List<PlayerEntry> roster;
        public List<PlayerEntry> starting_xi;
    }

    [Serializable]
    public class KitEntry
    {
        public int[] primary;
        public int[] secondary;
    }

    [Serializable]
    public class PlayerEntry
    {
        public string name;
        public int number;
        public int rating;
        public string pos;
    }

    public static TeamDatabase Load()
    {
        TextAsset asset = Resources.Load<TextAsset>("teams");
        if (asset == null)
        {
            Debug.LogWarning("teams.json not found in Resources");
            return null;
        }
        return JsonUtility.FromJson<TeamDatabase>(asset.text);
    }
}
